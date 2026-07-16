"""trading/brain/entry_vector.py — the microstructure feature vector recorded AT ENTRY.

Step 1 of the quality-gate rebuild (owner-approved 2026-07-16). The gate it replaces is a measured
no-op: `CRYPTO_MIN_SCORE=0.25` against observed scores of 9.74–340 filters nothing, and `final_score`
has ZERO correlation with realized profit (−0.031, n=260, 29.2% win, mean −0.213%) — the
highest-scoring quartile is the WORST. See `research/audits/quality-gate-falsified-20260716.md`.

Its replacement must be a DIRECT, CALIBRATED FORECAST of the trade's outcome, fitted on our own
purged out-of-sample data. That model cannot be fitted from what we record today, so this module
records the evidence first. It is a RECORDER, not a model: it decides nothing and gates nothing.

FIELD CHOICE IS EVIDENCE-DRIVEN, not a guess — two deep-research runs, 197 unique claims / 189 from
primary sources (`research/gate-rebuild/SYNTHESIS-AND-FIELD-LIST.md`). The three findings that shape
this vector, each of which contradicts what we assumed:

  1. **Book STATE beats order FLOW by 3-4x** at 1m/5m. Pre-event L2 state (spread, top-20 depth,
     top-20 imbalance) improves over baseline by +0.034 (1m) / +0.045 (5m); order flow adds only
     +0.010 over a pure book-shape baseline. So OFI is recorded but DEMOTED — the book state leads.
  2. **OFI's famous R²=65% is CONTEMPORANEOUS.** Its documented power lives at 3–5 SECONDS and turns
     slightly negative at later lags; we hold 15m–4h. It explains the move happening now, it does not
     forecast the next one.
  3. **Flow power is STATE-DEPENDENT and CLOCK-PHASED — and we recorded neither.** ETH's 1m increment
     runs +0.004 (calm) → +0.038 (stressed), ~10x. Order imbalance at QUARTER-HOUR clock marks
     forecasts perp returns at 4–12h and is monotonically weaker at 1m/5m marks; Binance perps burst
     in vol/volume at those marks, so "unconditional pooling across clock phases mixes structurally
     different regimes." A flat pooled model averages the signal toward zero — plausibly exactly the
     0.4922 we measure. **`liquidity_regime` and `clock_phase` are therefore Tier-1 fields.**

Reads RAM only (`binance_stream` mirror + `book_ofi`), so it adds no network call to the decision
path. Every miss is an honest None — never a fabricated value — and `_stale` records the age of what
we did read, so a later fit can audit staleness instead of trusting it.

    from trading.brain.entry_vector import entry_vector
    entry_vector("BTC/USDT:USDT")   # -> {"ev_spread_bps": .., "ev_liquidity_regime": "stressed", ...}
"""
from __future__ import annotations

import os
import time

# Clock marks that Binance perps actually burst on (research §1.3). Recorded as SECONDS SINCE each
# mark so a fit can condition on phase instead of pooling structurally different regimes together.
_CLOCK_MARKS_S = (60, 300, 900)

# Liquidity-regime cut points on spread (bps). Deliberately crude + explicit: the research says the
# REGIME matters ~10x, not that any particular boundary is right. Env-tunable so a fit can re-derive
# them from our own percentiles rather than inheriting someone else's dataset.
_CALM_MAX_BPS = float(os.getenv("EV_CALM_MAX_BPS", "2") or 2)
_STRESSED_MIN_BPS = float(os.getenv("EV_STRESSED_MIN_BPS", "8") or 8)


def enabled() -> bool:
    return os.getenv("ENTRY_VECTOR", "1").strip().lower() not in ("0", "false", "off")


def _norm(symbol: str) -> str:
    """Any caller's symbol -> Binance perp form (BTC/USDT:USDT -> BTCUSDT)."""
    return (symbol or "").upper().replace("/", "").split(":")[0]


def clock_phase(now: float | None = None) -> dict:
    """Seconds since each clock mark + the distance to the next one.

    Research §1.3: order-imbalance predictive power is strongest at QUARTER-HOUR marks and
    monotonically weaker at 1m/5m marks, and Binance perps show periodic vol/volume bursts at all
    three — so pooling across phases mixes different regimes. This is a CONDITIONER, not an alpha.
    """
    t = time.time() if now is None else now
    out: dict = {}
    for m in _CLOCK_MARKS_S:
        since = t % m
        out[f"ev_clock_since_{m}s"] = round(since, 2)
        out[f"ev_clock_to_next_{m}s"] = round(m - since, 2)
    return out


def liquidity_regime(spread_bps: float | None, depth_q: float | None = None) -> str | None:
    """calm | mixed | stressed — the conditioner order-flow power depends on (~10x swing).

    None (not a guess) when spread is unknown: an unconditioned row is worse than a missing one,
    because it silently pools a stressed observation with a calm one."""
    if spread_bps is None:
        return None
    if spread_bps <= _CALM_MAX_BPS:
        return "calm"
    if spread_bps >= _STRESSED_MIN_BPS:
        return "stressed"
    return "mixed"


def _book_state(sym: str) -> dict:
    """Tier-2: the L2 book STATE — the strongest predictor at our horizons (research §1.1).

    Deliberately computes depth/imbalance over the FULL 20 levels the mirror carries: the existing
    psychology engine reads 5, and the research's measured edge is specifically top-20."""
    out: dict = {"ev_spread_bps": None, "ev_obi_20": None, "ev_obi_l1": None,
                 "ev_depth_bid_20": None, "ev_depth_ask_20": None, "ev_mid": None,
                 "ev_microprice_dev_bps": None, "ev_book_age_s": None}
    try:
        from trading.broker_sense.binance_stream import get_mirror
        bk = get_mirror().book(sym, max_age_s=10.0)
        if not bk:
            return out
        bids, asks = bk.get("bids") or [], bk.get("asks") or []
        if not bids or not asks:
            return out
        bid, bq = float(bids[0][0]), float(bids[0][1])
        ask, aq = float(asks[0][0]), float(asks[0][1])
        if bid <= 0 or ask <= 0:
            return out
        mid = (bid + ask) / 2.0
        db = sum(float(q) for _, q in bids[:20])
        da = sum(float(q) for _, q in asks[:20])
        out["ev_mid"] = mid
        out["ev_spread_bps"] = round((ask - bid) / mid * 1e4, 4)
        out["ev_depth_bid_20"] = round(db, 4)
        out["ev_depth_ask_20"] = round(da, 4)
        if db + da > 0:
            out["ev_obi_20"] = round((db - da) / (db + da), 6)      # top-20 imbalance (the strong one)
        if bq + aq > 0:
            out["ev_obi_l1"] = round((bq - aq) / (bq + aq), 6)
            micro = (bid * aq + ask * bq) / (bq + aq)               # imbalance-weighted microprice
            out["ev_microprice_dev_bps"] = round((micro - mid) / mid * 1e4, 4)
        out["ev_book_age_s"] = round(time.time() - float(bk.get("ts") or 0), 3)
    except Exception:
        pass
    return out


def _flow(sym: str) -> dict:
    """Tier-3: order flow — recorded but DEMOTED (research §1.1/§1.2: 3-4x weaker than book state,
    and its power is contemporaneous at 3-5s while we hold 15m-4h)."""
    out: dict = {"ev_ofi": None, "ev_ofi_n": None, "ev_gofi": None, "ev_book_n": None,
                 "ev_taker_ratio": None, "ev_taker_imbalance": None}
    try:
        from trading.broker_sense import book_ofi
        s = book_ofi.series(sym)
        if s is not None and not s.empty:
            r = s.iloc[-1]
            # series() RENAMES the raw jsonl columns (ofi/gofi/n) to its BOOK_FIELDS contract
            # (of_ofi/of_gofi_book/of_book_n/of_ofi_n). Reading the raw names silently yields all
            # Nones with the data sitting right there — caught 2026-07-16 by live-verify, not tests.
            for k, col in (("ev_ofi", "of_ofi"), ("ev_ofi_n", "of_ofi_n"),
                           ("ev_gofi", "of_gofi_book"), ("ev_book_n", "of_book_n")):
                v = r.get(col)
                if v is not None and v == v:                       # NaN-safe
                    out[k] = float(v)
    except Exception:
        pass
    try:
        from trading.broker_sense.binance_stream import get_mirror
        tk = get_mirror().taker(sym)
        if tk:
            out["ev_taker_ratio"] = tk.get("buy_sell_ratio")
            out["ev_taker_imbalance"] = tk.get("imbalance")        # defined even one-sided
    except Exception:
        pass
    return out


def _carry(sym: str) -> dict:
    """Tier-4: positioning + carry. `funding_rate_entry` was None on every trade despite funding
    having 100% RAM coverage — that gap is fixed here."""
    out: dict = {"ev_funding_rate": None, "ev_next_funding_in_s": None, "ev_oi_usd": None,
                 "ev_oi_change_pct": None, "ev_crowd_long_pct": None, "ev_smart_long_pct": None,
                 "ev_liq_skew": None}
    try:
        from trading.broker_sense.binance_stream import get_mirror
        m = get_mirror()
        f = m.funding(sym)
        if f:
            out["ev_funding_rate"] = f.get("funding_rate")
            nf = f.get("next_funding_ts")
            if nf:
                out["ev_next_funding_in_s"] = round(max(0.0, nf / 1000.0 - time.time()), 1)
        st = m.stats(sym)
        if st:
            out["ev_oi_usd"] = st.get("open_interest_usd")
            out["ev_oi_change_pct"] = st.get("oi_change_pct")
            out["ev_crowd_long_pct"] = st.get("crowd_long_pct")
            out["ev_smart_long_pct"] = st.get("smart_long_pct")
    except Exception:
        pass
    try:
        from trading.broker_sense import binance_orderflow as of
        out["ev_liq_skew"] = of._liq_pressure(sym).get("liq_skew")
    except Exception:
        pass
    return out


def _volatility(sym: str) -> dict:
    """Tier-1: realized volatility of log returns — a regime conditioner AND the scale that sets
    triple-barrier widths (research §2: barriers = rolling std of log returns x multiplier). Without
    it recorded at entry, the labels a future fit derives are not reproducible."""
    out: dict = {"ev_sigma_logret_5m": None, "ev_vol_regime": None}
    try:
        import math
        from trading.broker_sense import binance_stream as bs
        rows = bs.ohlcv(sym, "5m", 60)                    # in-RAM mirror candles, no API
        if not rows or len(rows) < 12:
            return out
        closes = [float(r[4]) for r in rows if r and r[4]]
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
                if closes[i] > 0 and closes[i - 1] > 0]
        if len(rets) < 10:
            return out
        mean = sum(rets) / len(rets)
        sd = (sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5
        out["ev_sigma_logret_5m"] = round(sd, 8)
        # regime cut points are OUR percentiles later; this crude split is honest about being crude
        out["ev_vol_regime"] = ("low" if sd < 0.001 else "high" if sd > 0.004 else "mid")
    except Exception:
        pass
    return out


def _impact_inputs(sym: str) -> dict:
    """Tier-5: the three inputs the FITTED square-root impact law needs, plus the trailing stats.

    Research [52]: on Binance BTC/USD perps the law holds with **delta = 0.59** (not the textbook 0.5)
    as I = k*sigma_T*(Q/V_T)^delta, over a T = 1h trailing window. So slippage needs intended size Q
    (added by the caller — only the executor knows it), trailing 1h volatility sigma_T, and trailing
    1h volume V_T. [19] warns that the naive alternative our 20-level book invites — walking the book
    — UNDER-predicts impact, so the law is the right tool. [18] delta is regime-dependent (it collapses
    in thin books / liquidation cascades), so the regime fields are recorded alongside, and delta must
    be re-fit on OUR venue rather than imported.
    """
    out: dict = {"ev_sigma_1h": None, "ev_volume_1h": None, "ev_impact_delta_ref": 0.59}
    try:
        import math
        from trading.broker_sense import binance_stream as bs
        rows = bs.ohlcv(sym, "5m", 12)                     # ~1h of 5m bars from the RAM mirror
        if rows and len(rows) >= 6:
            closes = [float(r[4]) for r in rows if r and r[4]]
            rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
                    if closes[i] > 0 and closes[i - 1] > 0]
            if len(rets) >= 5:
                mu = sum(rets) / len(rets)
                out["ev_sigma_1h"] = round((sum((r - mu) ** 2 for r in rets)
                                            / (len(rets) - 1)) ** 0.5, 8)
        t = bs.get_mirror().ticker(sym)
        if t and t.get("quote_volume") is not None:
            # 24h quote volume / 24 = a crude 1h estimate. Named honestly: it is NOT the
            # recency-weighted V_T the paper fits, so a later fit must re-derive it.
            out["ev_volume_1h"] = round(float(t["quote_volume"]) / 24.0, 2)
    except Exception:
        pass
    return out


def _cross_asset(sym: str) -> dict:
    """Research [128]: cross-asset OFI adds nothing CONTEMPORANEOUSLY but DOES raise out-of-sample R²
    when FORECASTING — so each coin's row carries BTC/ETH flow. [129]: the structure is sparse (LASSO),
    which is why this records the two majors only and not all 200 coins."""
    out: dict = {"ev_btc_ofi_n": None, "ev_eth_ofi_n": None, "ev_btc_ret_5m": None}
    try:
        from trading.broker_sense import book_ofi
        for tag, ref in (("ev_btc_ofi_n", "BTCUSDT"), ("ev_eth_ofi_n", "ETHUSDT")):
            if ref == sym:
                continue                                    # don't duplicate a coin against itself
            s = book_ofi.series(ref)
            if s is not None and not s.empty:
                v = s.iloc[-1].get("of_ofi_n")
                if v is not None and v == v:
                    out[tag] = float(v)
    except Exception:
        pass
    try:
        from trading.broker_sense.binance_stream import get_mirror
        t = get_mirror().ticker("BTCUSDT")
        if t and t.get("pct_change") is not None:
            out["ev_btc_ret_5m"] = float(t["pct_change"])   # regime context: the whole market's tape
    except Exception:
        pass
    return out


def barriers(price: float | None, sigma: float | None, *, pt_mult: float = 1.0,
             sl_mult: float = 1.0, vertical_s: int = 14_400) -> dict:
    """Tier-5: the triple-barrier spec, recorded so the LABELS ARE REPRODUCIBLE.

    Research [14]: barriers are the rolling std of log returns x a multiple, plus a vertical time
    barrier — so an entry row must carry the point-in-time volatility, the multiples, the resulting
    upper/lower PRICE levels, and the vertical-barrier timestamp. [36][37]: sample-uniqueness weights
    additionally need the entry timestamp AND the eventual barrier-touch time t1 (filled at exit, not
    here) — overlapping labels are non-IID and must be down-weighted, so without these a future fit
    cannot even weight its samples correctly.
    """
    out: dict = {"ev_pt_mult": pt_mult, "ev_sl_mult": sl_mult,
                 "ev_vertical_barrier_s": vertical_s,
                 "ev_vertical_barrier_ts": round(time.time() + vertical_s, 3),
                 "ev_pt_price": None, "ev_sl_price": None}
    try:
        if price and sigma and price > 0 and sigma > 0:
            out["ev_pt_price"] = round(price * (1.0 + pt_mult * sigma), 10)
            out["ev_sl_price"] = round(price * (1.0 - sl_mult * sigma), 10)
    except Exception:
        pass
    return out


def costs(sym: str, *, size_usd: float | None = None, entry_type: str = "taker") -> dict:
    """Tier-5: the net-edge cost terms. Research [72]: a fee-only model inflates annualized return
    from 2.726 to 4.308 (+58%) and Sharpe 2.049 -> 2.506 versus a fully-costed run — fees AND slippage
    AND funding carry, or the target is a fiction. [43]: at just 0.3 ticks of slippage most tested
    configurations went NEGATIVE. [89][124]: the fill assumption can FLIP the sign of the result —
    taker profited through the 2025-10-10 flash crash while maker took catastrophic adverse selection
    — so the intended fill side is recorded, not assumed.
    """
    out: dict = {"ev_entry_type": entry_type, "ev_size_usd": size_usd,
                 "ev_fee_bps": None, "ev_slippage_bps_est": None, "ev_participation": None}
    try:
        # Binance USD-M perp defaults; env-overridable rather than hardcoded per CONVENTIONS.
        out["ev_fee_bps"] = float(os.getenv("EV_TAKER_FEE_BPS", "4.5") or 4.5) \
            if entry_type == "taker" else float(os.getenv("EV_MAKER_FEE_BPS", "1.8") or 1.8)
        imp = _impact_inputs(sym)
        sig, vol = imp.get("ev_sigma_1h"), imp.get("ev_volume_1h")
        if size_usd and sig and vol and vol > 0:
            part = float(size_usd) / float(vol)             # participation rate Q/V_T
            out["ev_participation"] = round(part, 10)
            # I = k * sigma_T * (Q/V_T)^delta  — the FITTED Binance-perp form [52], k=1 pending our
            # own re-fit ([17][18]: the exponent is venue- and regime-specific; do not trust 0.5).
            out["ev_slippage_bps_est"] = round(sig * (part ** 0.59) * 1e4, 4)
    except Exception:
        pass
    return out


def entry_vector(symbol: str, *, market: str = "crypto", price: float | None = None,
                 size_usd: float | None = None, entry_type: str = "taker") -> dict:
    """The full entry-time vector for `symbol`. RAM-only; never raises.

    `price`/`size_usd`/`entry_type` come from the CALLER (only the executor knows the intended size
    and fill side) and unlock the Tier-5 label + cost fields — without them the row still records
    every market-state field, but a future fit cannot reconstruct the labels or the net edge.

    Returns {} when disabled or non-crypto. Missing inputs are honest Nones. `ev_ts` + the per-block
    age fields let a later fit audit staleness rather than assume freshness [48].
    """
    if not enabled() or str(market).lower() != "crypto":
        return {}
    sym = _norm(symbol)
    if not sym:
        return {}
    t0 = time.time()
    out: dict = {"ev_ts": round(t0, 3), "ev_symbol": sym}
    try:
        out.update(_book_state(sym))          # Tier-2 — the strongest predictor [62][135]
        out.update(_flow(sym))                # Tier-3 — demoted [61]; kept for the horizon test
        out.update(_carry(sym))               # Tier-4
        out.update(_volatility(sym))          # Tier-1 conditioner + label scale [14][34]
        out.update(clock_phase())             # Tier-1 conditioner [66][67][68]
        out.update(_cross_asset(sym))         # [128] cross-asset OFI helps FORECASTING (not impact)
        out.update(_impact_inputs(sym))       # Tier-5 [52] square-root law inputs
        out.update(costs(sym, size_usd=size_usd, entry_type=entry_type))   # Tier-5 [72][43][89]
        out.update(barriers(price if price is not None else out.get("ev_mid"),
                            out.get("ev_sigma_logret_5m")))                # Tier-5 [14][36]
        # Tier-1: the regime the flow features are only meaningful WITHIN [63][136]
        out["ev_liquidity_regime"] = liquidity_regime(out.get("ev_spread_bps"),
                                                      out.get("ev_depth_bid_20"))
        # [48]: feed vs order latency must be separable — record when WE finished reading, so a fit
        # can measure how stale the inputs already were at decision time instead of assuming zero.
        out["ev_build_ms"] = round((time.time() - t0) * 1000.0, 2)
        out["ev_decision_ts"] = round(time.time(), 3)
        filled = sum(1 for k, v in out.items() if k.startswith("ev_") and v is not None)
        out["ev_filled"] = filled                       # coverage meter — honest sample-size signal
    except Exception:
        pass
    return out
