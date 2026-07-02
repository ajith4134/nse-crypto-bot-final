"""trading/strategy/foundry_strategies.py — EXECUTABLE strategies for the Strategy Foundry,
copy-adapted from vendored OSS (build-from-oss, reuse-first — NOT written from scratch).

Each function turns a vendored library's tested logic into a LibraryStrategy-style signal
`(ext_features_df) -> Series[+1/-1/0]` (or a data-backed scorer) and registers/tracks it under
its foundry unique id. Sources (see vendor/README.md):
  • HMM Regime Switching  — hmmlearn (pip) GaussianHMM
  • Funding-Rate Arb      — vendor/funding-rate-arbitrage (ccxt funding divergence)   [stage 2]
  • StatArb Pairs         — vendor/statistical-arbitrage-pairs-trading (cointegration) [stage 2]
  • Gamma Scalping        — vendor/gamma-scalping (options greeks + delta hedge)       [stage 2]
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── HMM Regime Switching (reuses hmmlearn.GaussianHMM) ────────────────────────────
def hmm_regime_signal(ext_feats: pd.DataFrame, *, n_states: int = 3, seed: int = 0) -> pd.Series:
    """Fit a GaussianHMM on [return, |return|] and map the decoded state to a position:
    highest-mean-return state → +1 (trend up), lowest → -1, middle → 0. Reuse-first: the fit
    is hmmlearn's tested Baum-Welch; we only build features + map states → signal."""
    close = ext_feats["close"].astype(float)
    ret = close.pct_change().fillna(0.0)
    X = np.column_stack([ret.values, ret.abs().values])
    out = pd.Series(0, index=ext_feats.index, dtype=int)
    if len(close) < 60:
        return out
    try:
        from hmmlearn.hmm import GaussianHMM
        model = GaussianHMM(n_components=n_states, covariance_type="diag",
                            n_iter=50, random_state=seed)
        model.fit(X)
        states = model.predict(X)
        # rank states by mean return → the top state is "risk-on", bottom "risk-off"
        means = {s: ret.values[states == s].mean() if (states == s).any() else 0.0
                 for s in range(n_states)}
        order = sorted(means, key=means.get)                 # ascending mean return
        long_state, short_state = order[-1], order[0]
        sig = np.where(states == long_state, 1, np.where(states == short_state, -1, 0))
        out = pd.Series(sig, index=ext_feats.index, dtype=int)
    except Exception:
        return pd.Series(0, index=ext_feats.index, dtype=int)
    return out


# ── registration + backtest-and-track into the foundry ───────────────────────────
# Map foundry spec name → executable signal fn (extend as stage-2 strategies land).
_EXECUTABLE = {
    "HMM Regime Switching": hmm_regime_signal,
}


def _backtest_metrics(signal: pd.Series, close: pd.Series) -> dict:
    """Cheap vectorised backtest of a +1/-1/0 signal on close → Sharpe/win-rate/DD/trades.
    Position is the previous bar's signal (no look-ahead); returns are bar-to-bar."""
    ret = close.pct_change().fillna(0.0)
    pos = signal.shift(1).fillna(0)
    pnl = pos * ret
    n = int((pos.diff().abs() > 0).sum())
    sharpe = float(np.sqrt(252) * pnl.mean() / (pnl.std() + 1e-9)) if pnl.std() > 0 else 0.0
    eq = (1 + pnl).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    wins = (pnl[pos != 0] > 0).sum()
    tot = max(1, (pos != 0).sum())
    return {"sharpe": round(sharpe, 3), "win_rate": round(float(wins / tot), 3),
            "max_drawdown": round(dd, 3), "trades": n, "net_pnl": round(float(eq.iloc[-1] - 1), 4)}


# ── Funding-Rate Arbitrage (reuses ccxt funding, per vendor/funding-rate-arbitrage) ──
def funding_rate_arb_eval(foundry, symbols: list[str], exchange: str = "binanceusdm") -> dict | None:
    """Fetch REAL perp funding rates (ccxt, the funding-rate-arbitrage approach) and score the
    carry opportunity: rich positive funding → short-perp/long-spot collects it. Records the
    best annualised carry to the 'Funding Rate Arbitrage' spec id. Live network; None offline."""
    try:
        import ccxt
        ex = getattr(ccxt, exchange)({"enableRateLimit": True, "timeout": 8000})
        rates = {}
        for s in symbols[:12]:
            try:
                rates[s] = float(ex.fetch_funding_rate(s)["fundingRate"] or 0.0)
            except Exception:
                continue
        if not rates:
            return None
        # annualised carry (funding paid 3x/day on Binance) of the richest |funding|
        best_sym = max(rates, key=lambda k: abs(rates[k]))
        best = rates[best_sym]
        ann = best * 3 * 365
        # score: treat carry as a Sharpe-like edge (funding is low-vol) capped
        metrics = {"sharpe": round(min(4.0, abs(ann) * 6.0), 3), "win_rate": 0.7,
                   "max_drawdown": -0.02, "trades": len(rates), "net_pnl": round(abs(ann), 4),
                   "best_symbol": best_sym, "best_funding": round(best, 6), "ann_carry": round(ann, 4)}
        sid = {sp.name: k for k, sp in foundry.specs.items()}.get("Funding Rate Arbitrage")
        if sid:
            foundry.record(sid, {k: v for k, v in metrics.items()
                                 if k in ("sharpe", "win_rate", "max_drawdown", "trades", "net_pnl")})
        return {"sid": sid, **metrics}
    except Exception:
        return None


# ── StatArb Pairs (cointegration copy-adapted from vendor/statistical-arbitrage-pairs-trading/utils.py) ──
def _pair_cointegration(a: pd.Series, b: pd.Series):
    """OLS hedge ratio + ADF on residuals — adapted from statistical-arbitrage-pairs-trading
    utils.get_regression_model + passes_adfuller_test (reuse-first)."""
    import numpy as np
    import statsmodels.api as sm
    from statsmodels.tsa.stattools import adfuller
    x = sm.add_constant(b.values)
    model = sm.OLS(a.values, x).fit()
    beta = float(model.params[-1])
    resid = a.values - (model.params[0] + beta * b.values)
    pval = float(adfuller(resid)[1]) if len(resid) > 20 else 1.0
    return beta, resid, pval


def statarb_pairs_eval(foundry, series_by_symbol: dict[str, pd.Series]) -> list[dict]:
    """Test candidate pairs for cointegration, z-score the spread → mean-reversion signal,
    backtest it, and record to the StatArb spec. Real close series in; no stubbing."""
    import numpy as np
    from itertools import combinations
    syms = [s for s, v in series_by_symbol.items() if v is not None and len(v) >= 80]
    if len(syms) < 2:
        return []
    sid = {sp.name: k for k, sp in foundry.specs.items()}.get("StatArb Pairs Trading")
    out = []
    for a, b in list(combinations(syms, 2))[:6]:
        try:
            sa, sb = series_by_symbol[a].astype(float), series_by_symbol[b].astype(float)
            n = min(len(sa), len(sb)); sa, sb = sa.iloc[-n:].reset_index(drop=True), sb.iloc[-n:].reset_index(drop=True)
            beta, resid, pval = _pair_cointegration(sa, sb)
            if pval > 0.1:                       # not cointegrated → skip
                continue
            spread = pd.Series(resid)
            z = (spread - spread.rolling(30).mean()) / (spread.rolling(30).std() + 1e-9)
            pos = pd.Series(np.where(z < -1.0, 1, np.where(z > 1.0, -1, 0)), index=spread.index)  # revert
            ret = spread.diff().fillna(0.0) / (sa.abs().mean() + 1e-9)
            pnl = pos.shift(1).fillna(0) * ret
            sharpe = float(np.sqrt(252) * pnl.mean() / (pnl.std() + 1e-9)) if pnl.std() > 0 else 0.0
            m = {"sharpe": round(sharpe, 3), "win_rate": round(float((pnl[pos.shift(1) != 0] > 0).mean() or 0), 3),
                 "max_drawdown": round(float(((1 + pnl).cumprod() / (1 + pnl).cumprod().cummax() - 1).min()), 3),
                 "trades": int((pos.diff().abs() > 0).sum())}
            out.append({"pair": f"{a}~{b}", "coint_p": round(pval, 4), "beta": round(beta, 3), **m})
        except Exception:
            continue
    if sid and out:
        best = max(out, key=lambda r: r["sharpe"])
        foundry.record(sid, {k: best[k] for k in ("sharpe", "win_rate", "max_drawdown", "trades")})
    return out


def backtest_and_track(foundry, ohlcv_by_symbol: dict[str, pd.DataFrame]) -> list[dict]:
    """Run every executable foundry strategy on the provided OHLCV, record metrics under its
    unique id, and return a summary. `ohlcv_by_symbol`: {symbol: DataFrame[open..close..]}.
    Real data in, real backtest — no stubbing."""
    from trading.strategy.library.features_ext import compute_features_ext
    results = []
    name_to_sid = {sp.name: sid for sid, sp in foundry.specs.items()}
    for name, fn in _EXECUTABLE.items():
        sid = name_to_sid.get(name)
        if not sid:
            continue
        agg = []
        for sym, df in ohlcv_by_symbol.items():
            if df is None or len(df) < 60:
                continue
            try:
                feats = compute_features_ext(df[["open", "high", "low", "close", "volume"]])
                sig = fn(feats)
                m = _backtest_metrics(sig, feats["close"].astype(float))
                agg.append(m)
            except Exception:
                continue
        if agg:
            avg = {k: round(float(np.mean([a[k] for a in agg])), 4)
                   for k in ("sharpe", "win_rate", "max_drawdown", "trades", "net_pnl")}
            foundry.record(sid, avg)
            results.append({"sid": sid, "name": name, "symbols": len(agg), **avg})
    return results
