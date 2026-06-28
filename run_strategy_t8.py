"""run_strategy_t8.py — Trading Phase T8.1 (Strategy genome + operators + walk-forward
backtest) offline demo + status.

Drives the network-INDEPENDENT strategy-evolution substrate end to end on deterministic
synthetic OHLCV (NO network, NO API keys, NO new deps, fully reproducible). Every T8.1
piece lights up on the same seeded data:

  1. build deterministic synthetic OHLCV (seeded geometric random walk, ~800 bars) for a
     CRYPTO symbol and an NSE-like symbol; compute the causal feature frame for each.
  2. demonstrate walk_forward_folds() — the out-of-sample fold splitter that keeps fitness
     OOS-only (overfitting guardrail substrate for T8.2). All scoring below is on the OOS
     tail (the union of the walk-forward test blocks); the initial train block is ignored
     for T8.1.
  3. create a small random population (12 strategies, fixed-seed random_strategy, split
     across CRYPTO + NSE feature sets), backtest each on its market's OOS tail and print a
     ranked leaderboard by sharpe / total_return / profit_factor.
  4. one generation of evolution: take the global top-2, crossover() + mutate() them into
     children, backtest the children OOS, and show whether a child beat its parents.
  5. pretty-print a couple of example genomes via Strategy.to_dict().

Everything is pure numpy/pandas CPU logic on synthetic bars — the same genome/operators/
backtest run on REAL crypto (ccxt) + NSE (OpenAlgo) OHLCV once the evolution loop (T8.3)
feeds them live frames, and survivors are scored on the REAL T5 trade journal (T8.2).

Usage:
    .venv/bin/python run_strategy_t8.py
"""
from __future__ import annotations

import json
import sys
import warnings

# vectorbt/scipy emit benign RuntimeWarnings (empty slices, all-NaN folds, div-by-zero in
# Sharpe on flat blocks) on the synthetic demo data — silence them so the demo output stays
# clean and deterministic. The underlying math is guarded inside trading/strategy.
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from trading.strategy import (
    backtest_signal,
    compute_features,
    crossover,
    fitness,
    market_features,
    mutate,
    passes_guardrails,
    pbo_cscv,
    random_strategy,
    walk_forward_folds,
)

# Markets the demo evolves over, each with its own seeded synthetic series so the two
# populations face genuinely different price paths (different drift/vol regimes).
_MARKETS = {
    # symbol             market    seed  start    drift     vol
    "BTC/USDT":   ("CRYPTO", 11, 64000.0, 0.0006, 0.028),
    "RELIANCE":   ("NSE",    23,  2800.0, 0.0003, 0.014),
}
_N_BARS = 800
_POP_SIZE = 12
_POP_SEED = 8081
_N_FOLDS = 4

# ── T8.3 (DEAP NSGA-II evolution loop) demo knobs ──────────────────────────────
# Kept modest so the runner finishes quickly; lenient-ish dsr_min so the promotion
# path is illustrative on synthetic data. Cached module-level (built once).
_EVO_MARKET = "CRYPTO"
_EVO_POP = 16
_EVO_GENS = 4
_EVO_SEED = 4242
_EVO_DSR_MIN = 0.0
_EVO_PROMOTE_TOP = 5
_DEMO_EVOLUTION: dict | None = None


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def synth_ohlcv(n: int, seed: int, *, start: float, drift: float, vol: float) -> pd.DataFrame:
    """Deterministic seeded geometric random walk → OHLCV frame (no lookahead in caller).

    close follows exp(cumsum(normal(drift, vol))); open is the prior close; high/low wrap
    the open/close envelope so high>=max(open,close) and low<=min(open,close) always.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = start
    open_[1:] = close[:-1]
    base_hi = np.maximum(open_, close)
    base_lo = np.minimum(open_, close)
    high = base_hi * (1.0 + np.abs(rng.normal(0.0, vol / 2.0, n)))
    low = base_lo * (1.0 - np.abs(rng.normal(0.0, vol / 2.0, n)))
    volume = rng.uniform(1_000.0, 5_000.0, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def _oos_slice(feats: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Return (OOS-tail feature frame, walk-forward folds) for the given feature frame.

    The OOS tail is the union of all walk-forward test blocks (everything from the first
    test_start to the end) — the initial train block is reserved/ignored for T8.1.
    """
    folds = walk_forward_folds(len(feats), n_folds=_N_FOLDS, scheme="rolling")
    oos_start = folds[0]["test"][0]
    return feats.iloc[oos_start:].reset_index(drop=True), folds


def _score(strategy, oos_feats: pd.DataFrame) -> dict:
    """Backtest one strategy on its market's OOS feature tail → metrics dict."""
    sig = strategy.signal(oos_feats)
    return backtest_signal(sig, oos_feats).metrics


def _load_markets() -> dict:
    """Per-market full OHLCV + feature frame + OOS tail (deterministic, cached per call).

    Returns {market: {"ohlcv": df, "feats": df, "oos": df}} — the full frames feed the
    T8.2 walk-forward fitness/guardrails (which fold internally); the OOS tail keeps the
    T8.1 leaderboard backtest OOS-only.
    """
    data: dict[str, dict] = {}
    for symbol, (market, seed, start, drift, vol) in _MARKETS.items():
        ohlcv = synth_ohlcv(_N_BARS, seed, start=start, drift=drift, vol=vol)
        feats = compute_features(ohlcv)
        oos_tail, _ = _oos_slice(feats)
        data[market] = {"ohlcv": ohlcv, "feats": feats, "oos": oos_tail}
    return data


def _fold_returns(strategy, market_data: dict, n_folds: int) -> list[float]:
    """Per-fold OOS total-return vector for one strategy (the PBO performance blocks).

    Indicators are computed on the full causal history (strategy.signal on the full feature
    frame); only each walk-forward TEST block is scored — no in-sample leakage.
    """
    feats = market_data["feats"]
    sig = strategy.signal(feats)
    folds = walk_forward_folds(len(feats), n_folds=n_folds, scheme="rolling")
    out = []
    for f in folds:
        s, e = f["test"]
        res = backtest_signal(sig.iloc[s:e].reset_index(drop=True),
                              feats.iloc[s:e].reset_index(drop=True))
        out.append(float(res.metrics["total_return"]))
    return out


def build_demo_population() -> dict:
    """Deterministic strategy population + OOS leaderboard + T8.2 fitness/guardrails snapshot.

    Builds the two seeded synthetic markets, computes features, draws _POP_SIZE random
    strategies (fixed seed, alternating CRYPTO/NSE feature sets), and for each scores:
      • T8.1 OOS metrics (backtest on the walk-forward OOS tail),
      • T8.2 multi-objective fitness.score (OOS expectancy/Sharpe/-DD/-trade-penalty),
      • T8.2 overfitting guardrail (passes_guardrails, n_trials = population size),
    then computes a population-level PBO (CSCV) on the per-strategy×per-fold return matrix
    of the first market's configs. Returns a JSON-able snapshot (genomes as to_dict trees,
    NO equity curves) reused by the dashboard.

    Returns:
        {population: [{id, market, metrics, fitness_score, oos_fitness, guardrail, genome}],
         best: {...}, n: int, pbo: {...}, pbo_market: str, pbo_matrix: [[float]]}
        ranked best-first by (sharpe, total_return, profit_factor).
    """
    data = _load_markets()
    rng = np.random.default_rng(_POP_SEED)
    markets = list(_MARKETS.values())
    population = []
    strat_objs: list[tuple] = []
    for k in range(_POP_SIZE):
        market = markets[k % len(markets)][0]
        feats_names = market_features(market)
        strat = random_strategy(feats_names, rng, market=market, strat_id=f"S{k:02d}")
        md = data[market]
        metrics = _score(strat, md["oos"])
        fit = fitness(strat, md["ohlcv"], features=md["feats"], n_folds=_N_FOLDS)
        gr = passes_guardrails(strat, md["ohlcv"], n_trials=_POP_SIZE,
                               features=md["feats"], n_folds=_N_FOLDS)
        population.append({
            "id": strat.id, "market": market, "metrics": metrics,
            "fitness_score": float(fit.score),
            "oos_fitness": fit.oos_metrics,
            "guardrail": {"passed": bool(gr.passed),
                          "reasons": [str(r) for r in gr.reasons]},
            "genome": strat.to_dict(),
        })
        strat_objs.append((strat, market))

    population.sort(key=lambda p: _rank_key(p["metrics"]), reverse=True)

    # Population-level PBO (CSCV) on the first market's configs over 8 even time blocks.
    pbo_market = markets[0][0]
    matrix = [_fold_returns(s, data[m], 8) for s, m in strat_objs if m == pbo_market]
    pbo = pbo_cscv(np.array(matrix, dtype=float)) if len(matrix) >= 2 else {
        "pbo": None, "n_combos": 0, "median_logit": 0.0}
    return {"population": population, "best": population[0] if population else None,
            "n": len(population), "pbo": pbo, "pbo_market": pbo_market,
            "pbo_matrix": [[float(x) for x in row] for row in matrix]}


def build_demo_evolution() -> dict:
    """Run the T8.3 DEAP NSGA-II evolution loop once (cached) → JSON-able snapshot.

    Evolves a modest population (pop=_EVO_POP, gens=_EVO_GENS) of CRYPTO strategy
    genomes through OOS multi-objective fitness + NSGA-II Pareto selection, gates the
    survivors through the T8.2 overfitting guardrails, and promotes those that pass to
    NodeProtocol StrategyNodes. Returns EvolutionResult.as_dict() (history, pareto_size,
    n_promoted, best, registry) — deterministic, offline. Cached module-level so the
    dashboard endpoint and the runner share a single run.
    """
    global _DEMO_EVOLUTION
    if _DEMO_EVOLUTION is None:
        from trading.strategy.evolve import evolve
        ohlcv = synth_ohlcv(_N_BARS, _MARKETS["BTC/USDT"][1],
                            start=_MARKETS["BTC/USDT"][2], drift=_MARKETS["BTC/USDT"][3],
                            vol=_MARKETS["BTC/USDT"][4])
        feats = compute_features(ohlcv)
        result = evolve(ohlcv, market=_EVO_MARKET, features=feats,
                        pop_size=_EVO_POP, generations=_EVO_GENS, seed=_EVO_SEED,
                        n_folds=_N_FOLDS, dsr_min=_EVO_DSR_MIN, min_trades=5,
                        promote_top=_EVO_PROMOTE_TOP)
        _DEMO_EVOLUTION = result.as_dict()
    return _DEMO_EVOLUTION


def _rank_key(m: dict) -> tuple:
    """Leaderboard sort key: sharpe, then total_return, then a finite profit_factor."""
    pf = m.get("profit_factor", 0.0)
    pf = pf if np.isfinite(pf) else 1e9
    return (m.get("sharpe", 0.0), m.get("total_return", 0.0), pf)


def _fmt_metrics(m: dict) -> str:
    pf = m.get("profit_factor", 0.0)
    pf_s = "inf" if not np.isfinite(pf) else f"{pf:.2f}"
    return (f"sharpe={m['sharpe']:+6.2f}  ret={m['total_return']*100:+7.2f}%  "
            f"maxDD={m['max_drawdown']*100:6.2f}%  trades={m['n_trades']:>3}  "
            f"win={m['win_rate']:5.1f}%  pf={pf_s:>5}")


def _fmt_fitness(p: dict) -> str:
    """T8.2 leaderboard line: fitness score + the OOS components that drive it."""
    o = p.get("oos_fitness", {})
    pf = o.get("profit_factor", 0.0)
    return (f"score={p['fitness_score']:+8.3f}  exp={o.get('expectancy', 0.0)*100:+6.3f}%  "
            f"oosSharpe={o.get('oos_sharpe_mean', 0.0):+6.2f}  "
            f"trades={o.get('n_trades', 0):>3}  "
            f"maxDD={o.get('max_drawdown', 0.0)*100:6.2f}%")


def main() -> int:
    print("ML Network Brain — Trading T8.1 (Strategy genome + operators + "
          "walk-forward backtest) offline demo")

    _hdr("1. synthetic markets + feature frames (seeded, deterministic)")
    oos: dict[str, pd.DataFrame] = {}
    feat_len: dict[str, int] = {}
    for symbol, (market, seed, start, drift, vol) in _MARKETS.items():
        ohlcv = synth_ohlcv(_N_BARS, seed, start=start, drift=drift, vol=vol)
        feats = compute_features(ohlcv)
        tail, _ = _oos_slice(feats)
        oos[market] = tail
        feat_len[market] = len(feats)
        print(f"  {symbol:<10} [{market:<6}] bars={len(ohlcv)} -> features={len(feats)} "
              f"(after warm-up)  OOS-tail={len(tail)} bars")

    _hdr("2. walk_forward_folds() output (OOS-only fitness; train block reserved)")
    # Show the fold layout on the first market's full feature frame.
    first_market = next(iter(_MARKETS.values()))[0]
    folds = walk_forward_folds(feat_len[first_market], n_folds=_N_FOLDS, scheme="rolling")
    print(f"  [{first_market}] {feat_len[first_market]} feature rows, "
          f"{_N_FOLDS} rolling folds (test blocks union = OOS tail):")
    for k, f in enumerate(folds, 1):
        ts, te = f["test"]
        trs, tre = f["train"]
        print(f"  fold {k}: train=[{trs:>4},{tre:>4})  test=[{ts:>4},{te:>4})  "
              f"(test bars={te - ts})")

    _hdr(f"3. random population leaderboard ({_POP_SIZE} strategies, OOS-scored)")
    snap = build_demo_population()
    pop = snap["population"]
    print(f"  rank  id    market   {'metrics':<8}")
    for rank, p in enumerate(pop, 1):
        print(f"  #{rank:<3} {p['id']:<5} {p['market']:<7} {_fmt_metrics(p['metrics'])}")
    best = snap["best"]
    print(f"  best: {best['id']} [{best['market']}]  {_fmt_metrics(best['metrics'])}")

    _hdr("4. one generation of evolution (top-2 -> crossover + mutate -> children)")
    rng = np.random.default_rng(_POP_SEED + 1)
    p1, p2 = pop[0], pop[1]
    from trading.strategy import Strategy  # reconstruct genomes from their dicts
    parent_a = Strategy.from_dict(p1["genome"])
    parent_b = Strategy.from_dict(p2["genome"])
    print(f"  parent A = {p1['id']} [{p1['market']}]  {_fmt_metrics(p1['metrics'])}")
    print(f"  parent B = {p2['id']} [{p2['market']}]  {_fmt_metrics(p2['metrics'])}")

    child_a, child_b = crossover(parent_a, parent_b, rng)
    children = []
    for i, ch in enumerate((child_a, child_b)):
        ch = mutate(ch, market_features(ch.market), rng, n=2)
        ch.id = f"C{i:02d}"
        metrics = _score(ch, oos[ch.market])
        children.append((ch, metrics))
        print(f"  child  {ch.id} [{ch.market}] "
              f"parents={ch.provenance.get('parents')} "
              f"muts={ch.provenance.get('mutations')}")
        print(f"           {_fmt_metrics(metrics)}")

    parent_best = max(_rank_key(p1["metrics"]), _rank_key(p2["metrics"]))
    child_best_ch, child_best_m = max(children, key=lambda c: _rank_key(c[1]))
    beat = _rank_key(child_best_m) > parent_best
    verdict = "✅ a child BEAT both parents" if beat else "— no child beat the parents (this gen)"
    print(f"  verdict: {verdict} "
          f"(best child {child_best_ch.id} sharpe={child_best_m['sharpe']:+.2f} "
          f"vs best parent sharpe={max(p1['metrics']['sharpe'], p2['metrics']['sharpe']):+.2f})")

    _hdr("5. example genomes (Strategy.to_dict(), pretty JSON)")
    for p in (pop[0], pop[-1]):
        print(f"  --- {p['id']} [{p['market']}] ---")
        print(json.dumps(p["genome"], indent=2, default=str))

    # ── T8.2: journal-fitness + overfitting guardrails ──────────────────────────────
    print("\n" + "=" * 70)
    print("ML Network Brain — Trading T8.2 (journal-fitness + overfitting guardrails)")
    print("=" * 70)

    _hdr("6. multi-objective fitness leaderboard (OOS; expectancy/Sharpe/-DD/-trades)")
    ranked = sorted(snap["population"], key=lambda p: p["fitness_score"], reverse=True)
    print(f"  rank  id    market   fitness (multi-objective, OOS-only)")
    for rank, p in enumerate(ranked, 1):
        print(f"  #{rank:<3} {p['id']:<5} {p['market']:<7} {_fmt_fitness(p)}")
    top = ranked[0]
    print(f"  best-by-fitness: {top['id']} [{top['market']}]  {_fmt_fitness(top)}")

    _hdr(f"7. overfitting guardrails on the top 3 (n_trials = pop size = {_POP_SIZE})")
    data = _load_markets()
    n_passed = 0
    for p in ranked[:3]:
        strat = Strategy.from_dict(p["genome"])
        md = data[p["market"]]
        gr = passes_guardrails(strat, md["ohlcv"], n_trials=_POP_SIZE,
                               features=md["feats"], n_folds=_N_FOLDS)
        n_passed += int(gr.passed)
        verdict = "✅ PASS" if gr.passed else "❌ FAIL"
        print(f"  {p['id']} [{p['market']}]  {verdict}  "
              f"DSR={gr.dsr.get('dsr', 0.0):.3f}  PSR={gr.dsr.get('psr', 0.0):.3f}  "
              f"SR={gr.dsr.get('sr', 0.0):+.3f}  (vs bench {gr.dsr.get('sr_benchmark', 0.0):+.3f})")
        for reason in gr.reasons:
            print(f"        - {reason}")
    print(f"  → {n_passed}/3 of the top strategies cleared every guardrail "
          f"(random genomes rarely beat a {_POP_SIZE}-trial deflated Sharpe — expected).")

    _hdr("8. PBO via CSCV (probability of backtest overfitting, population-level)")
    matrix = snap["pbo_matrix"]
    pbo = snap["pbo"]
    rows = len(matrix)
    cols = len(matrix[0]) if matrix else 0
    print(f"  performance matrix: {rows} configs × {cols} time blocks "
          f"(market={snap['pbo_market']}, per-fold OOS total return)")
    pbo_v = pbo.get("pbo")
    pbo_s = "n/a" if pbo_v is None else f"{pbo_v:.3f}"
    print(f"  PBO = {pbo_s}  over {pbo.get('n_combos', 0)} symmetric IS/OOS splits "
          f"(median logit={pbo.get('median_logit', 0.0):+.3f})")
    print("  (PBO≈0 → the in-sample best stays good OOS; PBO→1 → overfit selection.)")

    # ── T8.3: DEAP NSGA-II evolution loop → NodeProtocol promotion ──────────────────
    print("\n" + "=" * 70)
    print("ML Network Brain — Trading T8.3 (DEAP NSGA-II evolution loop → "
          "NodeProtocol promotion)")
    print("=" * 70)

    from trading.strategy.evolve import evolve
    from trading.strategy.registry import promote
    from core.node_protocol import NodeProtocol

    evo_ohlcv = synth_ohlcv(_N_BARS, _MARKETS["BTC/USDT"][1],
                            start=_MARKETS["BTC/USDT"][2], drift=_MARKETS["BTC/USDT"][3],
                            vol=_MARKETS["BTC/USDT"][4])
    evo_feats = compute_features(evo_ohlcv)
    _hdr(f"9. evolving {_EVO_POP} CRYPTO genomes for {_EVO_GENS} generations "
         f"(μ+λ NSGA-II, OOS fitness, seed={_EVO_SEED})")
    result = evolve(evo_ohlcv, market=_EVO_MARKET, features=evo_feats,
                    pop_size=_EVO_POP, generations=_EVO_GENS, seed=_EVO_SEED,
                    n_folds=_N_FOLDS, dsr_min=_EVO_DSR_MIN, min_trades=5,
                    promote_top=_EVO_PROMOTE_TOP)

    print(f"  gen   best_score   mean_score   best OOS Sharpe   best OOS return")
    for h in result.history:
        print(f"  {h['gen']:>3}   {h['best_score']:>+10.4f}   {h['mean_score']:>+10.4f}   "
              f"{h['best_oos_sharpe']:>+15.4f}   {h['best_oos_return'] * 100:>+13.2f}%")
    if result.history:
        first, last = result.history[0]["best_score"], result.history[-1]["best_score"]
        trend = "improved" if last > first else ("flat" if last == first else "declined")
        print(f"  best_score {first:+.4f} (gen1) → {last:+.4f} (gen{len(result.history)}) "
              f"— {trend}")
    print(f"  evaluated={result.n_evaluated} genomes  Pareto-front size={len(result.pareto)}  "
          f"promoted nodes={len(result.promoted)}")

    _hdr("10. promotion PATH: wrap the best genome as a NodeProtocol StrategyNode")
    flist = market_features(_EVO_MARKET)
    best_strat = result.best[0]
    node = promote(best_strat, flist, metrics=best_strat._fit.oos_metrics)
    print(f"  promoted best genome {best_strat.id} → StrategyNode "
          f"name={node.name!r} kind={node.kind!r}")
    print(f"  isinstance(node, NodeProtocol) = {isinstance(node, NodeProtocol)}")
    # sample predict_proba on the OOS feature matrix (in the node's feature order)
    fmat = evo_feats[flist].tail(5).to_numpy()
    proba = node.predict_proba(fmat)
    print(f"  predict_proba(5×{len(flist)} feature matrix) = "
          f"{[round(float(p), 3) for p in proba]}  (p(long): long~0.9 / short~0.1 / flat 0.5)")
    if result.promoted:
        print(f"  → {len(result.promoted)} genome(s) cleared the T8.2 guardrails and were "
              f"registered as routable brain nodes.")
    else:
        print(f"  → 0 genomes cleared the strict T8.2 guardrails (honest: random/evolved "
              f"genomes rarely beat a multiple-testing-deflated Sharpe). The promotion bridge "
              f"above still demonstrates the genome→NodeProtocol path works end to end.")

    # confirm the dashboard snapshot builder is JSON-able + cached (built once).
    snap_evo = build_demo_evolution()
    print(f"  build_demo_evolution() snapshot: history={len(snap_evo['history'])} gens, "
          f"pareto_size={snap_evo['pareto_size']}, n_promoted={snap_evo['n_promoted']} "
          f"(JSON-able, cached for /api/trading/evolution/status)")

    print("\n✅ T8.1 + T8.2 + T8.3 demo complete (offline, deterministic): genome/operators/"
          "walk-forward backtest + multi-objective fitness + deflated-Sharpe/PBO guardrails "
          "+ NSGA-II evolution → NodeProtocol promotion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
