"""trading/direction/app_signals.py — turn EVERY captured broker filter/screener into a
direction signal (owner ask 2026-07-13: "lots of filters and screens aside from movement").

The filter lane's row only carried momentum + funding, so direction rode on 2 weak sources.
But the eyes (ui_market) capture far more — order book, taker flow, open interest, long/short
crowd, liquidations, option chain. This builds a (truth-ledger source, p_up) reading from
EACH kind that's available for the symbol, so the learned decider weights all of them by their
MEASURED edge (and the Direction X-Ray shows every one). Each source earns its own track record;
the proven ones start driving direction, the near-random ones fade. Zero extra network — reads
only what the browser already streamed. Never raises; returns [] when nothing is fresh.

Market-scoped: crypto reads futures microstructure; NSE reads option-chain PCR. The reliability
of each source stays separated by market in the truth ledger (see learned_direction.reliability).
"""
from __future__ import annotations

import math


# every filter/screener the brain tries to collect for EVERY trade's direction (owner
# 2026-07-13: "brain collecting all this every time every trade, not only on available").
ALL_KINDS = ["momentum", "funding", "taker", "book_imbalance", "longshort",
             "oi_trend", "liquidations", "pcr"]


def _sig(x: float) -> float:
    return min(0.98, max(0.02, float(x)))


def _num(d, *keys):
    """First present numeric among keys in dict d."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def signals(symbol: str, *, market: str = "crypto", row: dict | None = None) -> list:
    """Return [(source, p_up)] from every available captured filter/screener for `symbol`."""
    out: list = []
    row = row or {}
    try:
        from trading.broker_sense import ui_market as um
    except Exception:
        um = None

    # ── momentum (24h move) — from the row (cheap) ─────────────────────────────
    pct = row.get("pct_change")
    if pct is not None:
        out.append(("filter:momentum", _sig(1.0 / (1.0 + math.exp(-float(pct) / 5.0)))))

    if um is None:
        return out

    # ── funding: crowded +funding = crowded longs → short lean ─────────────────
    f = um.funding(symbol)
    fr = _num(f, "funding_rate") if f else row.get("funding_rate")
    if fr is not None:
        out.append(("filter:funding", _sig(0.5 - max(-0.4, min(0.4, float(fr) * 40.0)))))

    # ── taker flow: buy-heavy aggressor → long ─────────────────────────────────
    t = um.taker(symbol)
    tb = _num(t, "buy", "taker_buy_volume", "buy_volume")
    ts = _num(t, "sell", "taker_sell_volume", "sell_volume")
    if tb is not None and ts is not None and (tb + ts) > 0:
        out.append(("filter:taker", _sig(tb / (tb + ts))))

    # ── order-book imbalance: bid-heavy depth → long ───────────────────────────
    b = um.book(symbol)
    if isinstance(b, dict):
        bids, asks = b.get("bids") or [], b.get("asks") or []
        bv = sum(float(x[1]) for x in bids[:20] if len(x) > 1)
        av = sum(float(x[1]) for x in asks[:20] if len(x) > 1)
        if bv + av > 0:
            out.append(("filter:book_imbalance", _sig(bv / (bv + av))))

    # ── long/short crowd: extreme crowd positioning → mild contrarian ──────────
    ls = um.long_short(symbol)
    lr = _num(ls, "ratio", "long_short_ratio")
    if lr is None and ls:
        la, sa = _num(ls, "long_account", "long"), _num(ls, "short_account", "short")
        lr = (la / sa) if (la and sa) else None
    if lr is None:
        lr = row.get("long_short_ratio")
    if lr is not None and float(lr) > 0:
        out.append(("filter:longshort",
                    _sig(0.5 - max(-0.3, min(0.3, (float(lr) - 1.0) * 0.3)))))

    # ── open interest + price: OI rising with price = trend confirmation ───────
    oi = um.open_interest(symbol)
    oi_chg = _num(oi, "change_pct", "oi_change", "delta_pct")
    if oi_chg is not None and pct is not None:
        # OI up + price up → longs building (long); OI up + price down → shorts building (short)
        conf = math.tanh(abs(float(oi_chg)) / 5.0)
        lean = 0.5 + (0.4 * conf if float(pct) >= 0 else -0.4 * conf)
        out.append(("filter:oi_trend", _sig(lean)))

    # ── liquidations: shorts liquidated (short-side cascade) → price up → long ─
    try:
        liqs = um.recent_liquidations(symbol, n=50) or []
    except Exception:
        liqs = []
    if liqs:
        short_liq = sum(1 for x in liqs if str((x or {}).get("side", "")).lower() in ("short", "sell"))
        long_liq = sum(1 for x in liqs if str((x or {}).get("side", "")).lower() in ("long", "buy"))
        if short_liq + long_liq > 0:
            out.append(("filter:liquidations", _sig(short_liq / (short_liq + long_liq))))

    # ── option-chain PCR (NSE/options): PCR > 1 (put-heavy) = contrarian bullish ─
    oc = um.option_chain(symbol)
    pcr = _num(oc, "pcr", "put_call_ratio")
    if pcr is not None and pcr > 0:
        out.append(("filter:pcr", _sig(0.5 + max(-0.3, min(0.3, (float(pcr) - 1.0) * 0.3)))))

    return out


WANTED_FILE = "direction_collect_wanted.json"


def _ensure_streaming(symbol: str, market: str) -> None:
    """Decoupled request: record that direction WANTS this symbol's full filter set, so the
    funnel's tab pool pins it and its kinds (book/taker/OI/long-short) stream in for next
    time. The funnel owns the browser sessions; this just leaves a want (ban-safe WS on its
    side), non-blocking + fail-open so a trade never waits on the browser. TTL'd by the funnel."""
    try:
        from trading import state
        import time as _t
        mk = str(market).lower()

        def _upd(d):
            d = d or {}
            wanted = d.get(mk, {})
            wanted[str(symbol)] = round(_t.time(), 1)
            d[mk] = dict(sorted(wanted.items(), key=lambda kv: -kv[1])[:80])   # freshest 80
            return d
        state.mutate_json(WANTED_FILE, _upd, default={})
    except Exception:
        pass


def collect(symbol: str, *, market: str = "crypto", row: dict | None = None) -> dict:
    """COLLECT every filter/screener for this trade's direction — every time — and report
    coverage. Returns {signals, coverage:{present,missing,n_present,n_total}}. The brain
    gathers all kinds on each trade (not just whatever was already fresh); missing kinds
    trigger a stream-subscribe so they fill in, and the coverage is recorded so every trade
    shows WHAT it collected."""
    sigs = signals(symbol, market=market, row=row)
    present = sorted({s.split(":", 1)[1] for s, _ in sigs})
    missing = [k for k in ALL_KINDS if k not in present]
    coverage = {"present": present, "missing": missing,
                "n_present": len(present), "n_total": len(ALL_KINDS)}
    if missing:
        _ensure_streaming(symbol, market)          # fill the gaps for next time (ban-safe)
    return {"signals": sigs, "coverage": coverage}
