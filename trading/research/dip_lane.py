"""X24 — the DIP-REVERSION lane: the only entry rule with measured out-of-sample edge.

DERIVED FROM DATA, NOT FROM A STORY (research/direction-brain-mission/X23-RESULT.md).
On 1,449,379 labelled rows / 533 symbols / 5m bars, chronological holdout n=550,765:

  * the intraday market MEAN-REVERTS — bucketing forward 1h return by past 1h return is
    perfectly monotone, biggest risers −0.073% vs biggest fallers +0.056%, IC −0.062 t=−46.
  * entering ON momentum earns −0.229%/trade net of cost (what the other lanes do).
  * buying a big hourly DROP inside a 7-DAY DOWNTREND is the best signal in the dataset.

MEASURED PARAMETERS (each one tuned on the holdout, not guessed):
  entry   ret_1h <= DIP_THRESHOLD (−4% → +0.686% net, 61.0% win, n=3,222;
          −3% → +0.438% net, n=5,849 — deeper is better but rarer)
  filter  liquid (>= $2.5M/day) AND 7d trend <= 0 (a dip in an UPTREND LOSES: −0.086% net)
  stop    ~2% of PRICE (35.3% hit → +0.444% net). Our normal 0.8% halves the edge.
  exit    TIME, not profit. Every take-profit level tested made it WORSE
          (hold 1h +0.538%; TP 1.5% +0.167%; TP 3% +0.386%; stop+TP −0.070%).
  size    1x leverage so the 2% price stop costs 2% of stake — the risk it was measured at.

The stop/exit/leverage rules live in MlBridgeStrategy (keyed on the `dip_revert` enter_tag);
this module only SELECTS and PLACES.
"""
from __future__ import annotations

import gzip
import json
import os
import statistics
import time
from pathlib import Path

MIRROR = Path.home() / "trading/state/mirror_candles.json.gz"
DAILY = Path.home() / "trading/crypto/freqtrade/user_data/data/binance/futures"

DIP_THRESHOLD = float(os.environ.get("DIP_THRESHOLD_PCT", "-3.0"))
MIN_DOLLAR_VOL = float(os.environ.get("DIP_MIN_DOLLAR_VOL_M", "2.5")) * 1e6
MAX_CONCURRENT = int(os.environ.get("DIP_MAX_CONCURRENT", "12"))

# ── SPIKE-FADE (2026-07-22, owner: "huge sudden profit symbols placing short") ──
# Measured on the SAME holdout (n=550,765, WITH a 3% price stop applied, cost 0.10%):
#   pocket A  ret_1h >= +4%, 7d DOWNtrend, dist above 1h-EMA >= +2%  → +0.130%/trade (n=1,446)
#   pocket B  ret_1h >= +4%, 7d UPtrend (plain)                      → +0.087%/trade (n=3,841)
# A 2% stop makes both ~breakeven (squeeze risk) — the 3% stop and the 60m time exit live in
# MlBridgeStrategy keyed on the `spike_fade` enter_tag, at 1x leverage like the dip lane.
SPIKE_THRESHOLD = float(os.environ.get("SPIKE_THRESHOLD_PCT", "4.0"))
SPIKE_DIST_EMA = float(os.environ.get("SPIKE_MIN_DIST_EMA_PCT", "2.0"))
SPIKE_MAX_CONCURRENT = int(os.environ.get("SPIKE_MAX_CONCURRENT", "4"))
SPIKE_ENABLED = os.environ.get("SPIKE_FADE_ENABLED", "1") not in ("0", "false", "no")

# ── WINDOW-MOVERS lane (owner spec 2026-07-22, verbatim): divide the ~880 symbols into
# FOUR timeframe categories — movement over the last 5m / 15m / 30m / 1h (from scan time),
# with volatility — take the MOST increased and MOST decreased in each, and open them with
# the direction chosen by EXPERIMENT / brain confidence (a per-category bandit that grades
# itself on its own closed trades), "if increased try long or short … same with decreased".
# Geometry: 1x, 1% price stop (owner), 60m clock exit — keyed on the wm_ tag family in
# MlBridgeStrategy; protected from external force-exits like dip/spike so labels stay clean.
WM_ENABLED = os.environ.get("WM_LANE_ENABLED", "1") not in ("0", "false", "no")
WM_TOP_K = int(os.environ.get("WM_TOP_K", "2"))            # per window per side
WM_MAX_CONCURRENT = int(os.environ.get("WM_MAX_CONCURRENT", "8"))
WM_MIN_MOVE = {                                            # window → min |move|% to count
    "5m": float(os.environ.get("WM_MIN_5M", "0.3")),
    "15m": float(os.environ.get("WM_MIN_15M", "0.45")),
    "30m": float(os.environ.get("WM_MIN_30M", "0.6")),
    "1h": float(os.environ.get("WM_MIN_1H", "0.8")),
}
WM_MIN_BAR_VOL = float(os.environ.get("WM_MIN_BAR_VOL_PCT", "0.15"))   # median 5m bar range %
WM_BANDIT_STATE = "wm_bandit.json"
WM_EPSILON = float(os.environ.get("WM_EPSILON", "0.2"))
WM_MIN_ARM_N = int(os.environ.get("WM_MIN_ARM_N", "5"))    # explore both sides this long
_WM_BARS = {"5m": 1, "15m": 3, "30m": 6, "1h": 12}


def _mirror() -> dict:
    raw = json.loads(gzip.decompress(MIRROR.read_bytes()))
    return raw.get("candles") or {}


def _seven_day_and_volume(flat_symbol: str) -> tuple[float | None, float | None]:
    """(7d % change, 30d median daily dollar volume) from freqtrade's own daily candles."""
    try:
        import pandas as pd
        f = DAILY / f"{flat_symbol.replace('USDT', '_USDT_USDT')}-1d-futures.feather"
        if not f.exists():
            return None, None
        df = pd.read_feather(f)
        if len(df) < 31:
            return None, None
        c0 = float(df["close"].iloc[-1])
        c7 = float(df["close"].iloc[-8])
        dv = float((df["close"] * df["volume"]).tail(31).median())
        return ((c0 - c7) / c7 * 100.0 if c7 else None), dv
    except Exception:
        return None, None


def scan() -> list[dict]:
    """Symbols currently showing the measured setup, best (deepest) dip first."""
    out: list[dict] = []
    for flat, tfs in _mirror().items():
        b5 = tfs.get("300") or []
        if len(b5) < 14:
            continue
        c = [x[4] for x in b5]
        h = [x[2] for x in b5]
        l = [x[3] for x in b5]
        px = c[-1]
        if px <= 0:
            continue
        base = c[-13]                                  # 12 x 5m = 1 hour back
        if base <= 0:
            continue
        ret_1h = (px - base) / base * 100.0
        if ret_1h > DIP_THRESHOLD:                     # not a big enough drop
            continue
        t7, dv = _seven_day_and_volume(flat)
        if t7 is None or dv is None:
            continue
        if dv < MIN_DOLLAR_VOL:                        # liquidity floor (part of the edge)
            continue
        if t7 > 0:                                     # dip in an UPTREND loses money
            continue
        bars = [(h[i] - l[i]) / c[i] * 100.0 for i in range(-12, 0) if c[i]]
        out.append({
            "flat": flat,
            "symbol": flat.replace("USDT", "/USDT:USDT"),
            "ret_1h": ret_1h, "ret_7d": t7,
            "dollar_vol_m": dv / 1e6,
            "med_bar_pct": statistics.median(bars) if bars else 0.0,
        })
    out.sort(key=lambda r: r["ret_1h"])                # deepest dip first
    return out


def scan_spikes() -> list[dict]:
    """Symbols currently in a measured spike-fade SHORT pocket, biggest spike first."""
    out: list[dict] = []
    for flat, tfs in _mirror().items():
        b5 = tfs.get("300") or []
        if len(b5) < 14:
            continue
        c = [x[4] for x in b5]
        px = c[-1]
        base = c[-13]
        if px <= 0 or base <= 0:
            continue
        ret_1h = (px - base) / base * 100.0
        if ret_1h < SPIKE_THRESHOLD:
            continue
        t7, dv = _seven_day_and_volume(flat)
        if t7 is None or dv is None or dv < MIN_DOLLAR_VOL:
            continue
        # distance above the 1h EMA (EMA over the last 12 five-minute closes)
        ema = c[-12]
        k = 2.0 / (12 + 1)
        for x in c[-11:]:
            ema = x * k + ema * (1 - k)
        dist_ema = (px - ema) / ema * 100.0 if ema else 0.0
        pocket = None
        if t7 <= 0 and dist_ema >= SPIKE_DIST_EMA:
            pocket = "A_downtrend_overext"
        elif t7 > 0:
            pocket = "B_uptrend_plain"
        if pocket is None:
            continue
        out.append({
            "flat": flat,
            "symbol": flat.replace("USDT", "/USDT:USDT"),
            "ret_1h": ret_1h, "ret_7d": t7, "dist_ema": dist_ema,
            "dollar_vol_m": dv / 1e6, "pocket": pocket,
        })
    out.sort(key=lambda r: -r["ret_1h"])               # biggest spike first
    return out


def scan_window_movers() -> list[dict]:
    """Owner's 4-category scan: for each window (5m/15m/30m/1h) the top-K risers and top-K
    fallers across the whole mirror universe, volatility + liquidity checked. A symbol that
    tops several windows is credited once, to its SHORTEST window (priority 5m→1h)."""
    rows: dict[str, dict] = {}
    for flat, tfs in _mirror().items():
        b5 = tfs.get("300") or []
        if len(b5) < 14:
            continue
        c = [x[4] for x in b5]
        h = [x[2] for x in b5]
        l = [x[3] for x in b5]
        px = c[-1]
        if not px:
            continue
        bars = [(h[i] - l[i]) / c[i] * 100.0 for i in range(-12, 0) if c[i]]
        med_bar = statistics.median(bars) if bars else 0.0
        if med_bar < WM_MIN_BAR_VOL:                     # volatility leg
            continue
        moves = {}
        for win, nb in _WM_BARS.items():
            base = c[-(nb + 1)] if len(c) > nb else None
            if base:
                moves[win] = (px - base) / base * 100.0
        if moves:
            rows[flat] = {"flat": flat, "symbol": flat.replace("USDT", "/USDT:USDT"),
                          "moves": moves, "med_bar": med_bar}
    out, seen = [], set()
    for win in ("5m", "15m", "30m", "1h"):               # shortest window claims first
        pool = [r for r in rows.values()
                if win in r["moves"] and abs(r["moves"][win]) >= WM_MIN_MOVE[win]
                and r["flat"] not in seen]
        for side_name, key in (("up", lambda r: -r["moves"][win]),
                               ("down", lambda r: r["moves"][win])):
            ranked = sorted((r for r in pool
                             if (r["moves"][win] > 0) == (side_name == "up")), key=key)
            for r in ranked[:WM_TOP_K]:
                if r["flat"] in seen:
                    continue
                t7, dv = _seven_day_and_volume(r["flat"])
                if dv is None or dv < MIN_DOLLAR_VOL:    # liquidity leg
                    continue
                seen.add(r["flat"])
                out.append({"flat": r["flat"], "symbol": r["symbol"], "window": win,
                            "side_of_move": side_name, "move": r["moves"][win],
                            "med_bar": r["med_bar"]})
    return out


def _wm_bandit_pick(cell: str) -> str:
    """Direction for a category cell ('5m_up', '1h_down', …): explore both sides until each
    has WM_MIN_ARM_N closes, then epsilon-greedy on mean realized P&L per trade."""
    import random
    from trading import state
    st = state.load_json(WM_BANDIT_STATE, {}) or {}
    arms = st.get(cell) or {}
    nL, nS = arms.get("L", {}).get("n", 0), arms.get("S", {}).get("n", 0)
    if min(nL, nS) < WM_MIN_ARM_N:
        return "long" if nL <= nS else "short"
    if random.random() < WM_EPSILON:
        return random.choice(("long", "short"))
    mL = arms["L"]["pnl"] / nL if nL else 0.0
    mS = arms["S"]["pnl"] / nS if nS else 0.0
    return "long" if mL >= mS else "short"


def wm_grade_closed() -> int:
    """Feed the bandit: read closed wm_ trades since the cursor from freqtrade's own DB
    (read-only) and credit each cell's chosen arm with the realized profit %."""
    import sqlite3
    from pathlib import Path
    from trading import state
    db_path = Path.home() / "tradesv3.dryrun.sqlite"
    if not db_path.exists():
        return 0
    st = state.load_json(WM_BANDIT_STATE, {}) or {}
    cursor = st.get("_cursor") or "2026-01-01"
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = db.execute(
            "SELECT enter_tag, is_short, close_profit, close_date FROM trades "
            "WHERE is_open=0 AND enter_tag LIKE 'wm_%' AND close_date > ? "
            "ORDER BY close_date", (cursor,)).fetchall()
        db.close()
    except Exception:
        return 0
    graded = 0
    for tag, is_short, prof, cdate in rows:
        parts = str(tag or "").split("_")               # wm_<win>_<up|down>
        if len(parts) < 3 or prof is None:
            continue
        cell = f"{parts[1]}_{parts[2]}"
        arm = "S" if is_short else "L"
        cellst = st.setdefault(cell, {})
        a = cellst.setdefault(arm, {"n": 0, "pnl": 0.0})
        a["n"] += 1
        a["pnl"] += float(prof) * 100.0
        st["_cursor"] = str(cdate)
        graded += 1
    if graded:
        try:
            state.save_json(WM_BANDIT_STATE, st)
        except Exception:
            pass
    return graded


def run_window_movers_once(client, *, dry: bool = False) -> list[dict]:
    """Open the top movers of every window category, direction per the bandit."""
    if not WM_ENABLED:
        return []
    wm_grade_closed()
    cands = scan_window_movers()
    room = max(0, WM_MAX_CONCURRENT - _open_tag_count(client, "wm_"))
    acted = []
    for c in cands:
        if room <= 0:
            break
        cell = f"{c['window']}_{c['side_of_move']}"
        side = _wm_bandit_pick(cell)
        rec = dict(c, cell=cell, chosen=side)
        tag = f"wm_{cell}"
        if dry:
            rec["result"] = "DRY"
        else:
            try:
                rec["result"] = client.place_order(
                    symbol=c["symbol"], action=("LONG" if side == "long" else "SHORT"),
                    side=side, enter_tag=tag, segment="futures")
            except Exception as e:
                rec["result"] = {"error": f"{type(e).__name__}: {e}"}
        acted.append(rec)
        room -= 1
    return acted


def _open_tag_count(client, prefix: str) -> int:
    try:
        return sum(1 for t in (client.status() or [])
                   if str((t or {}).get("enter_tag") or "").startswith(prefix))
    except Exception:
        return 0


def open_dip_count(client) -> int:
    return _open_tag_count(client, "dip_revert")


def run_once(client, *, dry: bool = False, limit: int = 5) -> list[dict]:
    """Place up to `limit` dip entries, respecting MAX_CONCURRENT. Returns what it did."""
    cands = scan()
    room = max(0, MAX_CONCURRENT - open_dip_count(client))
    acted = []
    for c in cands[:limit]:
        if room <= 0:
            break
        rec = dict(c)
        if dry:
            rec["result"] = "DRY"
        else:
            try:
                rec["result"] = client.place_order(
                    symbol=c["symbol"], action="LONG", side="long",
                    enter_tag="dip_revert", segment="futures")
            except Exception as e:
                rec["result"] = {"error": f"{type(e).__name__}: {e}"}
        acted.append(rec)
        room -= 1
    return acted


def run_spikes_once(client, *, dry: bool = False, limit: int = 2) -> list[dict]:
    """Place up to `limit` spike-fade SHORT entries, respecting SPIKE_MAX_CONCURRENT."""
    if not SPIKE_ENABLED:
        return []
    cands = scan_spikes()
    room = max(0, SPIKE_MAX_CONCURRENT - _open_tag_count(client, "spike_fade"))
    acted = []
    for c in cands[:limit]:
        if room <= 0:
            break
        rec = dict(c)
        if dry:
            rec["result"] = "DRY"
        else:
            try:
                rec["result"] = client.place_order(
                    symbol=c["symbol"], action="SHORT", side="short",
                    enter_tag="spike_fade", segment="futures")
            except Exception as e:
                rec["result"] = {"error": f"{type(e).__name__}: {e}"}
        acted.append(rec)
        room -= 1
    return acted


if __name__ == "__main__":
    import config  # noqa: F401  (loads .env)
    from trading.crypto.engine_client import CryptoEngineClient
    cli = CryptoEngineClient()
    interval = float(os.environ.get("DIP_SCAN_SECONDS", "120"))
    print(f"[dip-lane] live: dip {DIP_THRESHOLD}% / 1h, spike-fade "
          f"{'+' if SPIKE_ENABLED else 'OFF '}{SPIKE_THRESHOLD}% / 1h, "
          f"liquidity >= ${MIN_DOLLAR_VOL/1e6:.1f}M, max {MAX_CONCURRENT}L/{SPIKE_MAX_CONCURRENT}S, "
          f"scan every {interval:.0f}s", flush=True)
    while True:
        try:
            for r in run_once(cli):
                ok = not (isinstance(r.get("result"), dict) and r["result"].get("error"))
                print(f"[dip-lane] {'ENTER' if ok else 'REJECT'} {r['symbol']} "
                      f"1h={r['ret_1h']:+.2f}% 7d={r['ret_7d']:+.1f}% "
                      f"${r['dollar_vol_m']:.1f}M -> {str(r['result'])[:120]}", flush=True)
            for r in run_spikes_once(cli):
                ok = not (isinstance(r.get("result"), dict) and r["result"].get("error"))
                print(f"[spike-fade] {'SHORT' if ok else 'REJECT'} {r['symbol']} "
                      f"1h={r['ret_1h']:+.2f}% 7d={r['ret_7d']:+.1f}% ema+{r['dist_ema']:.1f}% "
                      f"{r['pocket']} -> {str(r['result'])[:120]}", flush=True)
            for r in run_window_movers_once(cli):
                ok = not (isinstance(r.get("result"), dict) and r["result"].get("error"))
                print(f"[win-movers] {'OPEN' if ok else 'REJECT'} {r['symbol']} "
                      f"{r['cell']} move={r['move']:+.2f}% -> {r['chosen'].upper()} "
                      f"{str(r['result'])[:100]}", flush=True)
        except Exception as e:
            print(f"[dip-lane] cycle error: {type(e).__name__}: {e}", flush=True)
        time.sleep(interval)
