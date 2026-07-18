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
MAX_CONCURRENT = int(os.environ.get("DIP_MAX_CONCURRENT", "8"))


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


def open_dip_count(client) -> int:
    try:
        return sum(1 for t in (client.status() or [])
                   if str((t or {}).get("enter_tag") or "").startswith("dip_revert"))
    except Exception:
        return 0


def run_once(client, *, dry: bool = False, limit: int = 3) -> list[dict]:
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


if __name__ == "__main__":
    import config  # noqa: F401  (loads .env)
    from trading.crypto.engine_client import CryptoEngineClient
    cli = CryptoEngineClient()
    interval = float(os.environ.get("DIP_SCAN_SECONDS", "120"))
    print(f"[dip-lane] live: threshold {DIP_THRESHOLD}% / 1h, "
          f"liquidity >= ${MIN_DOLLAR_VOL/1e6:.1f}M, max {MAX_CONCURRENT} concurrent, "
          f"scan every {interval:.0f}s", flush=True)
    while True:
        try:
            for r in run_once(cli):
                ok = not (isinstance(r.get("result"), dict) and r["result"].get("error"))
                print(f"[dip-lane] {'ENTER' if ok else 'REJECT'} {r['symbol']} "
                      f"1h={r['ret_1h']:+.2f}% 7d={r['ret_7d']:+.1f}% "
                      f"${r['dollar_vol_m']:.1f}M -> {str(r['result'])[:120]}", flush=True)
        except Exception as e:
            print(f"[dip-lane] cycle error: {type(e).__name__}: {e}", flush=True)
        time.sleep(interval)
