"""trading/crypto/freqtrade/percoin_decider.py — brain picks the BEST strategy PER COIN (Phase G+).

Where `LibraryBrainDecider` blends EVERY library strategy into one majority vote per symbol, this
decider instead, for each coin:

  1. vectorized-backtests every executable crypto signal strategy on THAT coin's recent 5m bars
     (position formed at bar i from the signal known at i, earns the i→i+1 return — no lookahead),
     scoring each by annualized Sharpe of its strategy-returns (+ win-rate, + activity guard),
  2. re-weights each candidate by the BRAIN's confidence (TradeOutcomeNet trained on the closed
     journal): final = sharpe · brain_weight  ("blend both"),
  3. picks the single best strategy IF its final score clears a minimum threshold AND its CURRENT
     signal is actionable — otherwise STAYS FLAT (no ensemble fallback),
  4. returns the same decision dict the executor already routes to Freqtrade, carrying the chosen
     strategy name as `tag` (→ Freqtrade enter_tag → visible per-coin on both dashboards).

Reuses `LibraryBrainDecider` for the live OHLCV feed, feature build and strategy set — so it stays
honest/offline-safe (FLAT when data or strategies are absent) and inherits the same caching.
"""
from __future__ import annotations

import math
import os
import time

import numpy as np

from trading.crypto.freqtrade.brain_executor import LibraryBrainDecider

# 5-minute bars → periods per year for Sharpe annualization (12/h · 24 · 365).
_PERIODS_PER_YEAR = 12 * 24 * 365
_MIN_ACTIVE_BARS = 5          # a strategy must have held a position on ≥ this many bars to be scored
# below this blended score → stay flat (no trade). ENV-TUNABLE (owner: "I want to see 100s of
# trades"): CRYPTO_MIN_SCORE lowers the bar so far more coins clear it → many more open trades.
# 0.5 = selective (quality); ~0.2-0.3 = high-throughput (paper learn-lab). This is the REAL lever
# for trade COUNT — the max_open_trades cap was never the binding constraint (brain selectivity was).
_MIN_FINAL_SCORE = float(os.environ.get("CRYPTO_MIN_SCORE", "0.5"))
_MIN_DEFLATED_PSR = float(os.environ.get("CRYPTO_MIN_PSR", "0.35"))   # Pillar-20 deflated-PSR floor
# ↑ ENV-tunable too: lower it (e.g. 0.1) alongside CRYPTO_MIN_SCORE for high-throughput paper runs.


class PerCoinBrainDecider(LibraryBrainDecider):
    """Pick the best-scoring strategy for each coin (backtest × brain), or stay flat."""

    def __init__(self, *args, min_final_score: float = _MIN_FINAL_SCORE,
                 min_active_bars: int = _MIN_ACTIVE_BARS, use_brain: bool = True,
                 dsr_min: float = _MIN_DEFLATED_PSR, **kw):
        # Need a real backtest WINDOW, not just the latest bar: compute_features_ext burns ~200 bars
        # of warmup, so fetch plenty more (default 720 = 60h of 5m) → ~500 usable feature rows.
        kw.setdefault("lookback", 720)
        super().__init__(*args, **kw)
        self._min_final = float(min_final_score)
        self._min_active = int(min_active_bars)
        self._use_brain = bool(use_brain)
        self._dsr_min = float(dsr_min)
        self._net = None            # lazily-built TradeOutcomeNet (cached by closed-trade count)
        self._net_count = -1
        self._net_ts = float("-inf")   # last closed-trades fetch (TTL below)
        self._bw_cache: dict = {}   # (symbol, direction) → (mono_ts, (mult, info))
        # PER-5m-BAR MEMO (2026-07-12 perf fix): tournament() is the expensive part
        # (~142 strategies × backtest + TabPFN, ~7.5s/symbol) and is DETERMINISTIC within a
        # candle bar — but funnel cycles run every ~1–2 min while bars close every 5 min, so
        # 3–4 consecutive cycles recompute the identical ranking. Cache it by (symbol, bar
        # epoch): repeat-in-bar cycles drop from ~7.5s/sym to ~0. Measured 86% of decide() is
        # cacheable per bar. Kill-switch: SCAN_MEMO=0.  (see research/perf/hardware-saturation-audit-20260712.md)
        self._tourn_cache: dict = {}   # symbol -> (bar_epoch, result)

    # ── brain confidence (global skill learned from the closed journal) ──────────
    _NET_TTL_S = 120.0     # closed trades change slowly; a fresher net isn't worth an HTTP storm

    def _brain_net(self):
        """TradeOutcomeNet over the crypto closed journal. None when unavailable/insufficient.

        TTL-cached: `_brain_weight` runs inside the per-strategy loop of every `decide()`, so
        without the TTL one funnel cycle refetched the FULL closed-trade history over HTTP
        ~(strategies × symbols) times — the 2026-07-05 run_cycle wedge."""
        if not self._use_brain:
            return None
        # cost-aware TTL: never re-attempt more often than 5× what the last refresh cost —
        # a refresh slower than the TTL previously meant decide() spent the WHOLE funnel
        # cycle refreshing (2026-07-07 10,820s cycle, entries all deadline-deferred).
        ttl = max(self._NET_TTL_S, 5.0 * getattr(self, "_net_cost_s", 0.0))
        if time.monotonic() - self._net_ts < ttl:
            return self._net
        self._net_ts = time.monotonic()      # stamp attempts too — a down API isn't hammered
        try:
            from trading.crypto.freqtrade_ingest import map_trade
            from trading.brain.trade_features import get_outcome_net
            t0 = time.monotonic()
            # Build LABELLED rows: map each native Freqtrade closed trade onto the journal schema and
            # stamp net_pnl from its realized profit_abs — without this the outcome label is uniform
            # (all None) and the net can never train (needs BOTH win & loss classes).
            native = [ft for ft in self.client_for_brain().closed_trades()
                      if isinstance(ft, dict)]
            if len(native) == self._net_count and self._net is not None:
                self._net_cost_s = time.monotonic() - t0     # count unchanged → skip the mapping
                return self._net
            # RE-FIT THROTTLE (2026-07-12 wedge fix): the outcome net is a 1000+-row OOF
            # cross-val fit — MINUTES on the cycle thread. It re-fit on EVERY closed-trade count
            # change, so a burst of opens/closes re-fit it nearly every decision → the funnel
            # wedged 39 min mid-fit (py-spy: _fit_oof). Re-fit at most every OUTCOME_NET_REFIT_S
            # (default 900s); between fits the cached net serves (slightly stale labels are fine
            # for a per-coin prior). A warm net older than that but with a changed count still
            # waits for the window. First fit (cold, _net is None) always runs.
            import os as _os
            _refit_s = float(_os.environ.get("OUTCOME_NET_REFIT_S", "900") or 900)
            if self._net is not None and (t0 - getattr(self, "_net_last_fit", 0.0)) < _refit_s:
                self._net_cost_s = time.monotonic() - t0     # throttled → keep the warm net
                return self._net
            rows = []
            for ft in native:
                # broker_ctx=False: live ticker context is wrong-by-construction for
                # historical trades AND cost 2 HTTP calls × ~1,100 trades per refresh.
                r = map_trade(ft, broker_ctx=False).to_dict()
                pnl = ft.get("profit_abs")
                if pnl is not None:
                    r["net_pnl"] = float(pnl)
                    r["net_pnl_crypto"] = float(pnl)
                rows.append(r)
            # cap the fit rows so a single re-fit stays fast (the OOF cross-val cost grows with
            # row count; the most-recent N trades carry the current regime). OUTCOME_NET_MAX_ROWS.
            _maxrows = int(_os.environ.get("OUTCOME_NET_MAX_ROWS", "800") or 800)
            if _maxrows > 0 and len(rows) > _maxrows:
                rows = rows[-_maxrows:]
            self._net = get_outcome_net(rows)
            self._net_count = len(native)                    # gate on the native count we saw
            self._net_last_fit = t0
            self._net_cost_s = time.monotonic() - t0
            return self._net
        except Exception:
            return self._net             # transient API failure → last good net (may be None)

    def client_for_brain(self):
        # the brain net trains on Freqtrade's own closed trades (independent of the dark dashboard)
        from trading.crypto.engine_client import CryptoEngineClient
        if getattr(self, "_brain_client", None) is None:
            self._brain_client = CryptoEngineClient()
        return self._brain_client

    def _brain_weight(self, symbol: str, direction: str, last_price: float) -> tuple[float, dict]:
        """Map the brain's win-probability for a coin+direction into a [0.5, 1.5] multiplier.

        Trained → use the predicted p_win for a synthetic entry; untrained → neutral 1.0 (so the
        per-coin backtest alone decides, honestly). Never raises."""
        net = self._brain_net()
        if net is None or not getattr(net, "trained", False):
            return 1.0, {"engine": getattr(net, "engine", "none"), "p_win": None}
        # PREDICTION TTL cache (2026-07-11): with the TabPFN engine, ONE predict_one is a
        # full transformer forward pass on CPU — uncached, one pass per underlying per
        # cycle held the funnel's main thread for 30+ min (options tournament), freezing
        # the hand/crawl/study/next-cycles behind it. The weight only moves when the net
        # retrains, so BRAIN_WEIGHT_TTL_S (default 900) staleness is honest.
        key = (symbol, direction)
        now = time.monotonic()
        ttl = float(os.environ.get("BRAIN_WEIGHT_TTL_S", "900") or 900)
        hit = self._bw_cache.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
        try:
            row = {"symbol": symbol, "direction": direction, "instrument_type": "PERP",
                   "entry_price": last_price, "current_price": last_price, "leverage": 1.0}
            p = net.predict_one(row).get("p_win")
            if p is None:
                out = (1.0, {"engine": net.engine, "p_win": None})
            else:
                out = (float(0.5 + max(0.0, min(1.0, p))),
                       {"engine": net.engine, "p_win": round(p, 4)})
            self._bw_cache[key] = (now, out)
            return out
        except Exception:
            return 1.0, {"engine": getattr(net, "engine", "none"), "p_win": None}

    # ── per-coin backtest of one strategy ────────────────────────────────────────
    @staticmethod
    def _backtest(signal: np.ndarray, close: np.ndarray, min_active: int) -> dict | None:
        """Sharpe + win-rate of following `signal` on `close`. Position at bar i (known at i) earns
        the i→i+1 return — strictly causal, no lookahead. None if too few active bars / degenerate."""
        n = min(len(signal), len(close))
        if n < min_active + 2:
            return None
        sig = np.asarray(signal[-n:], dtype=float)
        px = np.asarray(close[-n:], dtype=float)
        ret = np.diff(px) / np.where(px[:-1] == 0, np.nan, px[:-1])   # len n-1, i→i+1
        pos = sig[:-1]                                                # signal known at i
        strat_ret = pos * ret
        finite = np.isfinite(strat_ret)
        series = strat_ret[finite]                                   # full series (0 on flat bars)
        traded = strat_ret[finite & (pos != 0)]                      # only bars actually holding
        n_active = int(traded.size)
        if n_active < min_active or series.size < min_active:
            return None
        sd = float(np.std(series))
        if sd == 0.0:
            return None
        sharpe = float(np.mean(series)) / sd * math.sqrt(_PERIODS_PER_YEAR)
        wins = int(np.count_nonzero(traded > 0))
        win_rate = round(wins / n_active, 4)
        return {"sharpe": round(sharpe, 4), "win_rate": win_rate,
                "n_active": n_active, "cum_return": round(float(np.sum(series)), 6)}

    @staticmethod
    def _tf_seconds(tf: str) -> int:
        """'5m'->300, '15m'->900, '1h'->3600, '1d'->86400. Defaults to 300 on any miss."""
        try:
            n, unit = int(tf[:-1]), tf[-1].lower()
            return n * {"m": 60, "h": 3600, "d": 86400}.get(unit, 60)
        except Exception:
            return 300

    # ── the full 153-strategy tournament for one coin (the EXPENSIVE part) ────────
    def tournament(self, symbol: str) -> dict:
        """Per-5m-bar-memoized wrapper over the expensive tournament. Within one candle bar the
        ranking is deterministic, so repeat calls (consecutive funnel cycles) reuse the result
        instead of recomputing ~142 strategies. SCAN_MEMO=0 disables. Errors are never cached
        (so a transient no-bars miss retries next cycle)."""
        import os
        if os.environ.get("SCAN_MEMO", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return self._tournament_uncached(symbol)
        epoch = int(time.time() // self._tf_seconds(getattr(self, "_tf", "5m")))
        hit = self._tourn_cache.get(symbol)
        if hit is not None and hit[0] == epoch:
            return hit[1]
        result = self._tournament_uncached(symbol)
        if not result.get("error"):
            self._tourn_cache[symbol] = (epoch, result)
        return result

    def _tournament_uncached(self, symbol: str) -> dict:
        """Rank every executable strategy on `symbol`'s live bars — backtest × brain — and
        apply the deflated-Sharpe anti-overfit gate. This is the expensive teacher the
        distilled micro-policy (invent-beyond #4) compresses; decide() consumes it live.
        Returns {"error": reason} on any honest miss."""
        df = self._ohlcv(symbol)
        if df is None or len(df) < 40:
            return {"error": "no live bars"}
        from trading.strategy.library.features_ext import compute_features_ext
        try:
            feats = compute_features_ext(df[["open", "high", "low", "close", "volume"]])
        except Exception:
            return {"error": "feature build failed"}

        close = df["close"].to_numpy(dtype=float)
        last_price = float(close[-1])
        ranked = []
        sig_by_name: dict = {}
        for s in self.strategies():
            try:
                sig = np.asarray(s.make_signal(feats), dtype=float)
            except Exception:
                continue
            bt = self._backtest(sig, close, self._min_active)
            if bt is None:
                continue
            last = int(np.sign(sig[-1])) if len(sig) else 0
            bw, binfo = self._brain_weight(symbol, ("LONG" if last >= 0 else "SHORT"), last_price)
            final = bt["sharpe"] * bw
            sig_by_name[s.name] = sig
            ranked.append({"name": s.name, "last": last, "final": round(final, 4),
                           "brain_weight": round(bw, 3), "p_win": binfo.get("p_win"), **bt})

        if not ranked:
            return {"error": "no scorable strategy", "n_candidates": 0}
        ranked.sort(key=lambda r: r["final"], reverse=True)
        best = ranked[0]

        # Pillar-20 anti-overfit: the picker tried len(ranked) strategies and kept the best,
        # so its Sharpe is inflated by selection. Deflate it — the winner must beat the
        # expected MAXIMUM Sharpe of that many trials (Deflated-Sharpe intuition, López de Prado).
        from trading.strategy.guardrails import (expected_max_sharpe,
                                                  probabilistic_sharpe_ratio)
        cand_sr = [r["sharpe"] for r in ranked]
        var_sr = float(np.var(cand_sr, ddof=1)) if len(cand_sr) > 1 else 1.0
        sr_bench = expected_max_sharpe(var_sr, max(2, len(ranked)))
        deflated_psr = probabilistic_sharpe_ratio(
            best["sharpe"], max(best["n_active"], 2), sr_benchmark=sr_bench)
        return {"ranked": ranked, "best": best, "deflated_psr": deflated_psr,
                "deflated_ok": deflated_psr >= self._dsr_min, "sr_bench": sr_bench,
                "close": close, "last_price": last_price, "df": df,
                "winner_signal": sig_by_name.get(best["name"])}

    # ── the instruction: best strategy per coin, or flat ─────────────────────────
    def decide(self, market: str, symbol: str, price, *, in_position: bool) -> dict:
        if str(market).upper() != "CRYPTO":
            return {"action": "FLAT"}
        t = self.tournament(symbol)
        if t.get("error"):
            meta = {"reason": t["error"]}
            if "n_candidates" in t:
                meta["n_candidates"] = t["n_candidates"]
            return {"action": "FLAT", "_brain": meta}
        ranked, best = t["ranked"], t["best"]
        deflated_psr, deflated_ok, sr_bench = (t["deflated_psr"], t["deflated_ok"],
                                               t["sr_bench"])

        # gate: the winner must clear the score floor; if in a position, exit when the best
        # strategy no longer says long (net signal turned non-positive).
        meta = {"source": "per_coin_best", "chosen_strategy": best["name"],
                "final_score": best["final"], "sharpe": best["sharpe"], "win_rate": best["win_rate"],
                "brain_weight": best["brain_weight"], "p_win": best["p_win"],
                "n_candidates": len(ranked), "threshold": self._min_final,
                "deflated_psr": round(deflated_psr, 4), "deflated_ok": deflated_ok,
                "dsr_benchmark": round(sr_bench, 4),
                "runners_up": [r["name"] for r in ranked[1:4]],
                "confidence": round(min(1.0, max(0.0, best["final"] / max(self._min_final, 1e-9) / 4.0)), 3)}

        if in_position:
            action = "FLAT" if (best["final"] >= self._min_final and best["last"] > 0) else "EXIT"
            meta["action"] = "UP" if action == "FLAT" else "EXIT"
            return {"action": action, "size": 1.0, "tag": best["name"], "_brain": meta}

        if best["final"] < self._min_final or best["last"] == 0 or not deflated_ok:
            meta["action"] = "NEUTRAL"
            meta["reason"] = ("below threshold" if best["final"] < self._min_final
                              else "winner flat now" if best["last"] == 0
                              else f"deflated-Sharpe gate (PSR={deflated_psr:.3f} < {self._dsr_min})")
            return {"action": "FLAT", "size": 1.0, "tag": best["name"], "_brain": meta}

        action = "LONG" if best["last"] > 0 else "SHORT"
        meta["action"] = "UP" if action == "LONG" else "DOWN"
        return {"action": action, "size": 1.0, "tag": best["name"], "_brain": meta}


def per_coin_brain_decider(**kw):
    """Factory returning a decide_fn compatible with LiveTradeLoop(decide_fn=...)."""
    return PerCoinBrainDecider(**kw).decide
