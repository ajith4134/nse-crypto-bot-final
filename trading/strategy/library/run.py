"""trading/strategy/library/run.py — backtest the executable library + rank a leaderboard.

The active T8 feature: take every EXECUTABLE LibraryStrategy, build its +1/-1/0 signal on the
extended causal feature frame, score it OUT-OF-SAMPLE (walk-forward test-block union) via the
existing `backtest_signal`, and rank a leaderboard. Data-gated strategies are reported with
their gating data requirements — never fabricated metrics (honest-dashboard-wiring).

`build_library_snapshot()` returns a JSON-able snapshot (coverage + leaderboard + data-gated
list) cached for the dashboard. Deterministic + offline on seeded synthetic OHLCV; pass real
crypto/NSE frames in to score the same strategies on live history.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.backtest import backtest_signal, walk_forward_folds
from trading.strategy.library.features_ext import compute_features_ext
from trading.strategy.library.registry import get_registry

# Seeded synthetic markets (mirror run_strategy_t8) so the demo is deterministic + offline.
_SYNTH = {
    # market           seed  start    drift    vol
    "crypto_spot":   (11, 64000.0, 0.0006, 0.028),
    "crypto_futures": (17, 3200.0, 0.0005, 0.030),
    "nse_cash":      (23,  2800.0, 0.0003, 0.014),
    "nse_intraday":  (29,  1800.0, 0.0002, 0.011),
    "nse_futures":   (31, 44000.0, 0.0003, 0.013),
    "mcx_commodities": (37, 6100.0, 0.0002, 0.016),
}
_N_BARS = 900
_N_FOLDS = 4
_SNAPSHOT: dict | None = None


def synth_ohlcv(n: int, seed: int, *, start: float, drift: float, vol: float) -> pd.DataFrame:
    """Deterministic seeded geometric-random-walk OHLCV (same construction as run_strategy_t8)."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.empty(n); open_[0] = start; open_[1:] = close[:-1]
    hi = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, vol / 2.0, n)))
    lo = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, vol / 2.0, n)))
    volume = rng.uniform(1_000.0, 5_000.0, n)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": volume})


def _oos_tail(feats: pd.DataFrame):
    folds = walk_forward_folds(len(feats), n_folds=_N_FOLDS, scheme="rolling")
    return feats.iloc[folds[0]["test"][0]:].reset_index(drop=True)


def _score_one(strat, feats: pd.DataFrame) -> dict:
    """Signal on the full causal frame, scored on the OOS tail (no in-sample leakage)."""
    sig_full = strat.make_signal(feats)
    oos = _oos_tail(feats)
    sig_oos = sig_full.iloc[len(feats) - len(oos):].reset_index(drop=True)
    return backtest_signal(sig_oos, oos).metrics


def _rank_key(m: dict) -> tuple:
    pf = m.get("profit_factor", 0.0)
    pf = pf if np.isfinite(pf) else 1e9
    return (m.get("sharpe", 0.0), m.get("total_return", 0.0), pf)


def _pick_market(strat) -> str:
    """Pick a synthetic market a strategy applies to (first match), else crypto_spot."""
    for seg in strat.segments:
        if seg in _SYNTH:
            return seg
    return "crypto_spot"


def run_library(ohlcv_by_market: dict | None = None, *, with_errors: bool = False) -> dict:
    """Backtest every executable strategy and return ranked leaderboard + coverage.

    ohlcv_by_market: {segment: ohlcv_df}. If None, builds seeded synthetic frames per market.
    """
    reg = get_registry()
    if ohlcv_by_market is None:
        ohlcv_by_market = {m: synth_ohlcv(_N_BARS, s, start=st, drift=d, vol=v)
                           for m, (s, st, d, v) in _SYNTH.items()}
    feats_cache = {m: compute_features_ext(df) for m, df in ohlcv_by_market.items()}

    leaderboard, errors = [], []
    for strat in reg.executable():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if strat.data_backed:
                    # downloads its own real data (ccxt/Deribit/OpenAlgo), cached to disk
                    metrics = strat.backtest()
                    market = "live-data"
                else:
                    market = _pick_market(strat)
                    feats = feats_cache[market] if market in feats_cache else next(iter(feats_cache.values()))
                    metrics = _score_one(strat, feats)
            leaderboard.append({
                "name": strat.name, "category": strat.category, "family": strat.family,
                "market_tested": market, "segments": list(strat.segments),
                "oss_source": strat.oss_source, "metrics": metrics,
                "data_backed": bool(strat.data_backed),
            })
        except Exception as exc:
            errors.append({"name": strat.name, "error": f"{type(exc).__name__}: {exc}"})

    leaderboard.sort(key=lambda r: _rank_key(r["metrics"]), reverse=True)
    for rank, row in enumerate(leaderboard, 1):
        row["rank"] = rank

    gated = [{"name": s.name, "category": s.category, "family": s.family,
              "logic": s.logic, "segments": list(s.segments),
              "gating_reqs": s.gating_reqs, "oss_source": s.oss_source, "notes": s.notes}
             for s in reg.data_gated()]

    out = {
        "coverage": reg.coverage(),
        "leaderboard": leaderboard,
        "n_backtested": len(leaderboard),
        "data_gated": gated,
        "n_errors": len(errors),
        "evolution": "disabled (trading.strategy.control) — library is the active feature",
    }
    if with_errors:
        out["errors"] = errors
    return out


def build_library_snapshot(*, reload: bool = False) -> dict:
    """Cached JSON-able snapshot for the dashboard (built once on synthetic data)."""
    global _SNAPSHOT
    if _SNAPSHOT is None or reload:
        _SNAPSHOT = run_library(with_errors=True)
    return _SNAPSHOT


def _fmt(m: dict) -> str:
    pf = m.get("profit_factor", 0.0)
    pf_s = "inf" if not np.isfinite(pf) else f"{pf:.2f}"
    return (f"sharpe={m['sharpe']:+6.2f}  ret={m['total_return'] * 100:+7.2f}%  "
            f"maxDD={m['max_drawdown'] * 100:6.2f}%  trades={m['n_trades']:>3}  "
            f"win={m['win_rate']:5.1f}%  pf={pf_s:>5}")


def main() -> int:
    warnings.filterwarnings("ignore")
    print("ML Network Brain — Trading Strategy LIBRARY (curated institutional templates)\n"
          "Evolution/mutation/creation is GATED OFF — this runs the fixed library to see how "
          "the known strategies perform.\n")
    snap = run_library(with_errors=True)
    cov = snap["coverage"]

    print(f"=== coverage: {cov['total']} strategies "
          f"({cov['n_executable']} executable, {cov['n_data_gated']} data-gated) ===")
    print("  by category: " + ", ".join(f"{k}={v}" for k, v in cov["by_category"].items() if v))
    print("  by segment : " + ", ".join(f"{k}={v}" for k, v in cov["by_segment"].items()))

    lb = snap["leaderboard"]
    print(f"\n=== executable leaderboard (OOS, {snap['n_backtested']} backtested) — top 25 ===")
    print(f"  {'#':>3}  {'strategy':32} {'cat':18} metrics")
    for row in lb[:25]:
        print(f"  {row['rank']:>3}  {row['name']:32} {row['category']:18} {_fmt(row['metrics'])}")

    print(f"\n=== data-gated families ({len(snap['data_gated'])}) — sample by gating need ===")
    by_gate: dict[str, list] = {}
    for s in snap["data_gated"]:
        key = ",".join(s["gating_reqs"]) or "n/a"
        by_gate.setdefault(key, []).append(s["name"])
    for gate, names in sorted(by_gate.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{gate}] ({len(names)}): {', '.join(names[:6])}"
              + (" …" if len(names) > 6 else ""))

    if snap["n_errors"]:
        print(f"\n⚠ {snap['n_errors']} strategies errored during backtest:")
        for e in snap.get("errors", []):
            print(f"  - {e['name']}: {e['error']}")
    print(f"\n✅ library run complete ({snap['n_backtested']} OOS backtests, "
          f"{cov['n_data_gated']} catalogued data-gated). Evolution: {snap['evolution']}.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
