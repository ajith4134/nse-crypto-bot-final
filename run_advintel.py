"""run_advintel.py — Trading Phase T8 (DEFERRED) Advanced-Intelligence offline demo.

Drives the Group-B Advanced-Intelligence + Group-A engine modules end to end, fully
OFFLINE and deterministic (NO network, NO API keys, NO LLM required). Every data source
that would touch the network in live use is replaced here by an INJECTED stub fetcher /
seeded DataFrame, so the runner is reproducible and never leaves the box:

  (a) PortfolioRisk  — Riskfolio/PyPortfolioOpt VaR/CVaR/HRP/Kelly + report over a seeded
                       per-asset returns DataFrame (numpy fallbacks keep it crash-proof).
  (b) StressTester   — first-order scenario analysis over a couple of positions + an
                       ad-hoc "Nifty -5%" what_if shock.
  (c) FiiDiiFlows / NseAnnouncements / OnChainMetrics / LiquidationHeatmap — all wired with
                       INJECTED stub fetchers (deterministic seeded data; no NSE/Coinglass/
                       on-chain HTTP) → latest/trend, recent, fear_greed/sopr/mvrv, heatmap.
  (d) ArbitrageScanner — stub price/funding sources → cross-exchange spot arb + funding farm.
  (e) AutonomousResearcher — stub searcher + summarizer (no ddgs, no LLM) → research digest.
  (f) QLearningExit  — tabular Q-learning trained on synthetic exit trajectories → should_exit.

`build_demo_advintel()` returns a JSON-able snapshot for the dashboard, cached at module
level. Exit 0, fully offline.

Usage:
    . .venv/bin/activate && PYTHONPATH=. python run_advintel.py
"""
from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")  # heavy libs (riskfolio/pypfopt) emit benign warnings

import numpy as np
import pandas as pd

from trading.advintel.portfolio_risk import PortfolioRisk
from trading.advintel.stress import Position, StressTester
from trading.advintel.fii_dii import FiiDiiFlows
from trading.advintel.nse_announcements import NseAnnouncements
from trading.advintel.onchain import OnChainMetrics
from trading.advintel.liquidations import LiquidationHeatmap
from trading.advintel.arbitrage import ArbitrageScanner
from trading.brain.researcher import AutonomousResearcher
from trading.brain.rl_exit import QLearningExit


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def _to_jsonable(obj):
    """Recursively cast numpy scalars/arrays → native python for JSON payloads."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    return obj


# ══════════════════════════════════════════════════════════════════════════════════
# (a) PortfolioRisk — seeded per-asset RETURNS DataFrame
# ══════════════════════════════════════════════════════════════════════════════════
_RISK_ASSETS = ["RELIANCE", "INFY", "BTC", "ETH", "GOLD"]
# Per-asset (annualised-ish daily) drift + vol so VaR/CVaR/HRP/Kelly are meaningful.
_RISK_MU = np.array([0.0006, 0.0004, 0.0012, 0.0010, 0.0002])
_RISK_SIG = np.array([0.012, 0.014, 0.040, 0.045, 0.008])


def _seeded_returns(n: int = 504, seed: int = 7) -> pd.DataFrame:
    """Deterministic daily simple-return panel (rows=days, cols=symbols)."""
    rng = np.random.default_rng(seed)
    # mild positive cross-correlation via a shared market factor
    market = rng.normal(0.0, 0.006, size=(n, 1))
    idio = rng.normal(_RISK_MU, _RISK_SIG, size=(n, len(_RISK_ASSETS)))
    beta = np.array([1.0, 1.1, 1.6, 1.7, 0.3])
    rets = idio + market * beta
    return pd.DataFrame(rets, columns=_RISK_ASSETS)


# ══════════════════════════════════════════════════════════════════════════════════
# (b) StressTester — a couple of open positions
# ══════════════════════════════════════════════════════════════════════════════════
def _stress_positions() -> list:
    return [
        Position("RELIANCE", "equity", "LONG", quantity=100, entry_price=2900.0, beta=1.1),
        Position("BTCUSDT", "crypto", "SHORT", quantity=2, entry_price=60000.0, beta=1.0),
        Position("GOLDM", "commodity", "LONG", quantity=10, entry_price=72000.0, beta=0.6),
    ]


# ══════════════════════════════════════════════════════════════════════════════════
# (c) Stub fetchers for the gated data sources (deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
def _stub_fiidii_fetcher():
    """Deterministic raw FII/DII rows (most-recent-first), ₹cr — no NSE HTTP."""
    return [
        {"date": "2026-06-27", "fii_buy": 12500.0, "fii_sell": 11000.0,
         "dii_buy": 9800.0, "dii_sell": 9000.0},
        {"date": "2026-06-26", "fii_buy": 10200.0, "fii_sell": 12800.0,
         "dii_buy": 11200.0, "dii_sell": 9500.0},
        {"date": "2026-06-25", "fii_buy": 13100.0, "fii_sell": 12200.0,
         "dii_buy": 8800.0, "dii_sell": 9900.0},
        {"date": "2026-06-24", "fii_buy": 9900.0, "fii_sell": 11500.0,
         "dii_buy": 10400.0, "dii_sell": 8700.0},
        {"date": "2026-06-23", "fii_buy": 14200.0, "fii_sell": 11800.0,
         "dii_buy": 9100.0, "dii_sell": 9300.0},
    ]


def _stub_announcements_fetcher():
    """Deterministic raw NSE corporate-announcement rows — no NSE HTTP."""
    return [
        {"symbol": "RELIANCE", "subject": "Quarterly financial results for Q1 FY27",
         "datetime": "2026-06-27T18:30:00", "detail": "Board approved audited results."},
        {"symbol": "RELIANCE", "subject": "Board approves dividend and buyback",
         "datetime": "2026-06-27T18:45:00", "detail": "Capital return to shareholders."},
        {"symbol": "INFY", "subject": "Board meeting intimation",
         "datetime": "2026-06-26T09:15:00", "detail": "To consider Q1 results."},
        {"symbol": "TCS", "subject": "Bulk deal disclosure under Reg 7(2)",
         "datetime": "2026-06-26T16:00:00", "detail": "Bulk deal in equity shares."},
        {"symbol": "HDFCBANK", "subject": "Outcome of AGM — general update",
         "datetime": "2026-06-25T11:00:00", "detail": "Routine corporate update."},
    ]


def _stub_onchain_fetcher(kind: str) -> dict:
    """Deterministic on-chain stub: fetcher(kind) -> dict (alternative.me/bitcoin-data shapes)."""
    if kind == "fear_greed":
        return {"data": [{"value": "72", "value_classification": "Greed"}]}
    if kind == "sopr":
        return {"sopr": 1.04}
    if kind == "mvrv":
        return {"mvrvZscore": 2.1, "mvrv": 1.8}
    return {}


def _stub_liquidations_fetcher(symbol: str) -> dict:
    """Deterministic Coinglass-style liquidation levels — no key, no HTTP."""
    return {"levels": [
        {"price": 58000.0, "notional": 4.2e8, "side": "long"},
        {"price": 59500.0, "notional": 7.8e8, "side": "long"},
        {"price": 61000.0, "notional": 6.1e8, "side": "short"},
        {"price": 62500.0, "notional": 9.5e8, "side": "short"},
        {"price": 64000.0, "notional": 3.3e8, "side": "short"},
    ]}


# ══════════════════════════════════════════════════════════════════════════════════
# (d) ArbitrageScanner — stub price/funding sources
# ══════════════════════════════════════════════════════════════════════════════════
# A small, deterministic cross-exchange book where binance is cheaper than bybit (real
# spot spread) and funding diverges (bybit pays more → short bybit / long binance).
_ARB_PRICES = {
    ("binance", "BTC/USDT"): {"bid": 60000.0, "ask": 60010.0},
    ("bybit", "BTC/USDT"): {"bid": 60140.0, "ask": 60150.0},
}
_ARB_FUNDING = {
    ("binance", "BTC/USDT"): 0.00005,
    ("bybit", "BTC/USDT"): 0.00035,
}


def _stub_price_source(exchange: str, symbol: str) -> dict:
    return _ARB_PRICES.get((exchange, symbol), {})


def _stub_funding_source(exchange: str, symbol: str) -> float:
    return _ARB_FUNDING.get((exchange, symbol), 0.0)


# ══════════════════════════════════════════════════════════════════════════════════
# (e) AutonomousResearcher — stub searcher + summarizer (no ddgs, no LLM)
# ══════════════════════════════════════════════════════════════════════════════════
def _stub_searcher(query: str) -> list:
    """Deterministic fake web results — no network."""
    return [
        {"title": "Reliance Q1 profit beats estimates on retail strength",
         "href": "https://example.com/ril-q1",
         "body": "Reliance reported record quarterly profit; analysts upgrade on retail growth."},
        {"title": "Reliance announces buyback and higher dividend",
         "href": "https://example.com/ril-buyback",
         "body": "Board approves capital return; bullish FY guidance reiterated."},
        {"title": "Reliance telecom unit faces regulatory probe",
         "href": "https://example.com/ril-probe",
         "body": "A regulator opened an inquiry; modest legal-risk overhang on the stock."},
    ]


def _stub_summarizer(prompt: str) -> str:
    """Deterministic fake LLM summary (no real LLM call)."""
    return ("Reliance posted a record Q1 with retail-led growth [1] and announced a buyback "
            "plus a higher dividend [2], both bullish catalysts. The main risk is a telecom-unit "
            "regulatory probe [3]. Net: constructive, with a contained legal overhang.")


# ══════════════════════════════════════════════════════════════════════════════════
# (f) QLearningExit — synthetic exit trajectories
# ══════════════════════════════════════════════════════════════════════════════════
def _exit_trajectories() -> list:
    """Synthetic trajectories teaching: hold while edge persists, bank high R, cut anomalies.

    WINNER: rides 0→+2.5R — early steps HOLD (the future is brighter), the terminal high-R
            step EXITs to BANK the gain. LOSER: an anomaly trade that, if held, blows up from
            -1.5R to a catastrophic -3R bar — so cutting at -1.5R (state (0,1,1)) is optimal.
    Holding carries a small per-step cost; the blow-up bar carries a large holding cost so
    the agent genuinely learns to cut the losing-anomaly state rather than bleed into it.
    """
    winners, losers = [], []
    for _ in range(8):
        winners.append([
            {"unrealized_r": 0.2, "bars_held": 1, "anomaly_high": 0, "step_reward": -0.01},
            {"unrealized_r": 0.9, "bars_held": 4, "anomaly_high": 0, "step_reward": -0.01},
            {"unrealized_r": 1.8, "bars_held": 7, "anomaly_high": 0, "step_reward": -0.01},
            {"unrealized_r": 2.5, "bars_held": 10, "anomaly_high": 0,
             "step_reward": -0.01, "realized_pnl": 2.5},
        ])
        losers.append([
            {"unrealized_r": -0.3, "bars_held": 1, "anomaly_high": 1, "step_reward": -0.01},
            {"unrealized_r": -0.9, "bars_held": 4, "anomaly_high": 1, "step_reward": -0.01},
            {"unrealized_r": -1.5, "bars_held": 8, "anomaly_high": 1, "step_reward": -0.01},
            {"unrealized_r": -3.0, "bars_held": 12, "anomaly_high": 1,
             "step_reward": -3.0, "realized_pnl": -3.0},
        ])
    return winners + losers


# ══════════════════════════════════════════════════════════════════════════════════
# Dashboard snapshot (cached, JSON-able, deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
_CACHE: dict | None = None


def build_demo_advintel() -> dict:
    """JSON-able T8-deferred advanced-intelligence snapshot for the dashboard (cached)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    # (a) portfolio risk
    rets = _seeded_returns()
    pr = PortfolioRisk(rets, alpha=0.05)
    portfolio_risk = pr.report()

    # (b) stress
    positions = _stress_positions()
    tester = StressTester()
    stress = {
        "report": tester.report(positions),
        "scenario_analysis": tester.analyze(positions),
        "nifty_minus_5pct": tester.what_if(positions, {"equity": -0.05}),
    }

    # (c) gated sources via injected stubs
    fii = FiiDiiFlows(fetcher=_stub_fiidii_fetcher)
    fii_dii = {"latest": fii.latest(), "trend": fii.trend(n=5), "status": fii.status()}

    ann = NseAnnouncements(fetcher=_stub_announcements_fetcher)
    announcements = {
        "recent": ann.recent(n=10),
        "reliance": ann.for_symbol("RELIANCE"),
        "status": ann.status(),
    }

    oc = OnChainMetrics(fetcher=_stub_onchain_fetcher)
    onchain = {
        "fear_greed": oc.fear_greed(),
        "sopr": oc.sopr(),
        "mvrv": oc.mvrv(),
        "report": oc.report(),
    }

    liq = LiquidationHeatmap(fetcher=_stub_liquidations_fetcher)
    liquidations = {
        "heatmap": liq.heatmap("BTCUSDT"),
        "clusters": liq.clusters("BTCUSDT", n=3),
        "nearest": liq.nearest_cluster("BTCUSDT", price=60000.0),
        "status": liq.status(),
    }

    # (d) arbitrage
    arb = ArbitrageScanner(price_source=_stub_price_source,
                           funding_source=_stub_funding_source)
    arbitrage = {
        "spot": arb.scan_spot("BTC/USDT"),
        "funding_farm": arb.funding_farm("BTC/USDT"),
        "status": arb.status(),
    }

    # (e) autonomous research
    researcher = AutonomousResearcher(searcher=_stub_searcher, summarizer=_stub_summarizer)
    research = researcher.research("Reliance Q1 results and outlook")

    # (f) RL exit
    agent = QLearningExit(seed=0).train(_exit_trajectories(), epochs=200)
    rl_exit = {
        "status": agent.status(),
        "should_exit_high_R": agent.should_exit(2.5, 10, 0),
        "should_exit_winning_hold": agent.should_exit(0.5, 3, 0),
        "should_exit_losing_anomaly": agent.should_exit(-1.5, 8, 1),
        "p_exit": {
            "high_R": round(float(agent.predict_proba([[2.5, 10, 0]])[0]), 4),
            "early_winner": round(float(agent.predict_proba([[0.5, 3, 0]])[0]), 4),
            "losing_anomaly": round(float(agent.predict_proba([[-1.5, 8, 1]])[0]), 4),
        },
    }

    _CACHE = _to_jsonable({
        "portfolio_risk": portfolio_risk,
        "stress": stress,
        "fii_dii": fii_dii,
        "announcements": announcements,
        "onchain": onchain,
        "liquidations": liquidations,
        "arbitrage": arbitrage,
        "research": research,
        "rl_exit": rl_exit,
    })
    return _CACHE


def main() -> int:
    print("ML Network Brain — Trading T8 (DEFERRED) Advanced-Intelligence offline demo")

    snap = build_demo_advintel()

    # (a) portfolio risk
    _hdr("1. PortfolioRisk — Riskfolio/PyPortfolioOpt VaR/CVaR/HRP/Kelly (seeded returns)")
    pr = snap["portfolio_risk"]
    print(f"  assets={pr['n_assets']}  periods={pr['n_periods']}  alpha={pr['alpha']}")
    print(f"  VaR(5%)={pr['var']:+.5f}  CVaR(5%)={pr['cvar']:+.5f}  "
          f"max_drawdown={pr['max_drawdown']:+.4f}  sharpe={pr['sharpe']:.4f}")
    print(f"  HRP weights: { {k: round(v, 4) for k, v in pr['hrp_weights'].items()} }")
    print("  half-Kelly (capped) per asset:")
    for sym, k in pr["kelly"].items():
        print(f"      {sym:<10} kelly={k['kelly']:+.4f}  half={k['half_kelly']:+.4f}  "
              f"capped={k['capped']:+.4f}")

    # (b) stress
    _hdr("2. StressTester — scenario analysis + 'Nifty -5%' what-if")
    for name, r in snap["stress"]["scenario_analysis"].items():
        print(f"      {name:<16} total_pnl={r['total_pnl_impact']:+14.2f}  "
              f"pct_cap={r['pct_of_capital']:+7.2f}%  worst={r['worst_position']}")
    wi = snap["stress"]["nifty_minus_5pct"]
    print(f"  what_if Nifty -5%: total_pnl={wi['total_pnl_impact']:+.2f}  "
          f"pct_of_capital={wi['pct_of_capital']:+.4f}%  worst={wi['worst_position']['symbol']}")
    print(f"  worst scenario overall: {snap['stress']['report']['worst_scenario']}")

    # (c) gated sources (injected stubs)
    _hdr("3. FiiDiiFlows (stub fetcher) — latest + 5-day trend")
    fd = snap["fii_dii"]
    print(f"  latest: {fd['latest']}")
    t = fd["trend"]
    print(f"  trend({t['days']}d): fii_net_cum={t['fii_net_cum']:+.1f} ({t['fii_bias']})  "
          f"dii_net_cum={t['dii_net_cum']:+.1f} ({t['dii_bias']})")

    _hdr("4. NseAnnouncements (stub fetcher) — recent + by-type")
    print(f"  status: {json.dumps(snap['announcements']['status'], default=str)}")
    for a in snap["announcements"]["recent"][:4]:
        print(f"      {a['symbol']:<10} [{a['type']:<12}] {a['subject'][:50]}")

    _hdr("5. OnChainMetrics (stub fetcher) — Fear&Greed + SOPR + MVRV z-score")
    oc = snap["onchain"]
    print(f"  fear_greed: value={oc['fear_greed']['value']} ({oc['fear_greed']['label']})")
    print(f"  sopr: {oc['sopr']['value']} → {oc['sopr']['signal']}")
    print(f"  mvrv z-score: {oc['mvrv']['zscore']} → {oc['mvrv']['signal']}")

    _hdr("6. LiquidationHeatmap (stub fetcher) — clusters + nearest magnet")
    liq = snap["liquidations"]
    print(f"  status: {json.dumps(liq['status'], default=str)}")
    for c in liq["clusters"]["clusters"]:
        print(f"      price={c['price']:>10.1f}  notional={c['notional']:.3e}  side={c['side']}")
    n = liq["nearest"]
    print(f"  nearest cluster to 60000: price={n['cluster']['price']}  distance={n['distance']}")

    # (d) arbitrage
    _hdr("7. ArbitrageScanner (stub sources) — spot spread + funding farm")
    sp = snap["arbitrage"]["spot"]
    print(f"  spot: {sp['direction']}  spread%={sp['spread_pct']:.4f}  cost%={sp['cost_pct']:.4f}  "
          f"net%={sp['net_pct']:+.4f}  actionable={sp['actionable']}")
    ff = snap["arbitrage"]["funding_farm"]
    print(f"  funding farm: long@{ff['long_exch']} short@{ff['short_exch']}  "
          f"net_rate={ff['net_funding_rate']:+.6f}  ann_net%={ff['annualized_net_pct']:+.4f}  "
          f"profitable={ff['profitable']}")

    # (e) autonomous research
    _hdr("8. AutonomousResearcher (stub searcher+summarizer) — research digest")
    rs = snap["research"]
    print(f"  query={rs['query']!r}  n_sources={rs['n_sources']}  "
          f"available={rs['available']}  llm_used={rs['llm_used']}")
    print(f"  summary: {rs['summary'][:200]}")

    # (f) RL exit
    _hdr("9. QLearningExit — trained on synthetic exit trajectories")
    rl = snap["rl_exit"]
    print(f"  status: n_states={rl['status']['n_states']}  "
          f"epochs={rl['status']['epochs_trained']}  deep_rl={rl['status']['deep_rl']['available']}")
    print(f"  should_exit(R=+2.5, bars=10, anomaly=0) = {rl['should_exit_high_R']}  "
          f"(p_exit={rl['p_exit']['high_R']})")
    print(f"  should_exit(R=+0.5, bars=3,  anomaly=0) = {rl['should_exit_winning_hold']}  "
          f"(p_exit={rl['p_exit']['early_winner']})")
    print(f"  should_exit(R=-1.5, bars=8,  anomaly=1) = {rl['should_exit_losing_anomaly']}  "
          f"(p_exit={rl['p_exit']['losing_anomaly']})")

    _hdr("10. dashboard snapshot (build_demo_advintel — JSON-able, cached)")
    print(json.dumps(build_demo_advintel(), default=str)[:600] + "  ...")

    print("\n✅ T8 deferred advanced-intelligence demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
