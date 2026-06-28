"""run_brain_t8.py — Trading Phase T8.4 (Episodic Experience Bank + Semantic Memory) offline demo.

Drives the network-INDEPENDENT trading "brain memory" end to end, fully OFFLINE and
deterministic (NO network, NO API keys, NO LLM required):

  1. ExperienceBank (Case-Based Reasoning over closed trades). Every closed trade is
     indexed as a CASE: a deterministic numeric vector of its PRE-TRADE setup, stored
     with its OUTCOME (net P&L / R-multiple / win). The case base is loaded from the
     deterministic T5 demo journal (`build_demo_journal`) PLUS a handful of EXTRA
     synthetic ClosedTrades that form a clear WIN cluster and a clear LOSE cluster by
     market context (fear-greed / regime-confidence / relative-volume), so recall is
     illustrative. For a sample query setup we `recall()` the k analogous precedents and
     aggregate their outcomes — weighted by relevance × recency × importance — into a
     decision bias: expected win-rate, expected P&L, directional bias, confidence, plus
     the audit trail of precedent trade_ids. This is how analogous past trades BIAS a
     new decision. A LanceDB-backed bank (persisted to a tempdir) is also exercised when
     LanceDB is importable, wrapped in try/except; an in-memory numpy exact-kNN bank is
     the always-on deterministic path.

  2. SemanticMemory (free-text trade-lessons via mem0). Complements the numeric case
     base with a SEMANTIC memory of reflections that don't fit a feature vector
     ("breakouts after 2pm IST on low-volume names tend to fail"). Runs as a functional
     DRY-RUN keyword store offline; mem0 is installed and activates for REAL extraction/
     consolidation when MEM0_ENABLED=1 and an OpenAI-compatible LLM is configured.

`build_demo_experience()` returns a JSON-able snapshot (bank status + a sample recall +
semantic-memory status) for the dashboard, cached at module level.

Usage:
    .venv/bin/python run_brain_t8.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")  # lancedb emits a benign WARN on first table create

import numpy as np
import pandas as pd

from trading.brain.experience import ExperienceBank
from trading.brain.semantic import SemanticMemory
from trading.brain.continual import OnlineNode, ReplayBuffer, replay_retrain
from trading.brain.selfeval import AutoQuiz, reflect_and_store
from trading.brain.metalearn import MetaLearner
from trading.brain.patterns import PatternScanner
from trading.brain.regime import RegimeModel, RegimeGate
from trading.brain.picking import GPLearnFactorMiner, AssetPicker
from trading.brain.entryexit import EntryExitPolicy
from trading.brain.sentiment import SentimentScorer
from trading.brain.news import NewsItem, NewsResearcher, NewsSentimentNode
from trading.brain.skills import Skill, SkillLibrary
from trading.brain.observability import BrainTracer
from trading.brain.selfimprove import SelfImprover, DSPyOptimizer
from trading.brain.pipeline import BrainTradingPipeline
from trading.strategy import random_strategy, market_features
from trading.execution import KillSwitch, DailyCircuitBreaker
from trading.alerts import AlertDispatcher, TelegramChannel, Deduplicator, signal_event
from trading.alerts.config import AlertConfig
from trading.journal import ClosedTrade, TradeJournal
from run_journal_t5 import build_demo_journal


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def build_extra_trades() -> list:
    """Synthetic ClosedTrades forming a clear WIN cluster vs LOSE cluster by context.

    WIN cluster  — crypto perp LONGs in a high-conviction tape (fear_greed≈78,
                   regime_confidence≈82, relative_volume≈2.0): all winners.
    LOSE cluster — crypto perp LONGs in a fearful/low-conviction tape (fear_greed≈22,
                   regime_confidence≈28, relative_volume≈0.6): all losers.
    The setup vector keys on these context fields, so a query in either regime recalls
    its own cluster — demonstrating context-driven decision biasing.
    """
    win, lose = [], []

    def _ct(tid, sym, entry, exit_, fg, rc, rv, fr) -> ClosedTrade:
        return ClosedTrade(
            trade_id=tid, symbol=sym, exchange="binance", instrument_type="PERP",
            direction="LONG", product_type="ISOLATED", strategy_name="Momentum",
            setup_type="Swing", market_regime_entry="Trending", leverage=5.0,
            margin_used=1000.0, entry_datetime="2026-06-27T08:00:00",
            exit_datetime="2026-06-27T12:00:00", quantity=1.0,
            entry_price=entry, exit_price=exit_, initial_sl_price=entry * 0.97,
            funding_rate_entry=fr, fear_greed_index=fg, regime_confidence=rc,
            relative_volume=rv, brain_confidence_entry=0.7, brain_prediction="UP")

    # WIN cluster: high-conviction LONGs that worked (exit > entry).
    for i, (sym, e, x) in enumerate([("BTC/USDT", 60000.0, 63000.0),
                                     ("ETH/USDT", 3000.0, 3180.0),
                                     ("SOL/USDT", 140.0, 150.0),
                                     ("BNB/USDT", 580.0, 612.0)]):
        win.append(_ct(f"WIN{i+1}", sym, e, x, fg=78.0, rc=82.0, rv=2.0, fr=0.0001))

    # LOSE cluster: fearful/low-conviction LONGs that failed (exit < entry).
    for i, (sym, e, x) in enumerate([("BTC/USDT", 60000.0, 58200.0),
                                     ("ETH/USDT", 3000.0, 2880.0),
                                     ("SOL/USDT", 140.0, 132.0),
                                     ("BNB/USDT", 580.0, 556.0)]):
        lose.append(_ct(f"LOSE{i+1}", sym, e, x, fg=22.0, rc=28.0, rv=0.6, fr=-0.0002))

    # Record through a journal so charges → net P&L / R-multiple / win are REAL computed
    # numbers (a bare ClosedTrade has net_pnl=None); persist=False writes nothing to disk.
    j = TradeJournal(persist=False, daily_limit=999)
    for t in win + lose:
        j.record(t)
    return j.trades


# ── sample query: a NEW setup matching the high-conviction WIN regime ────────────────
SAMPLE_QUERY = {
    "instrument_type": "PERP", "direction": "LONG", "entry_hour": 8,
    "fear_greed_index": 77.0, "regime_confidence": 80.0, "relative_volume": 1.9,
    "funding_rate_entry": 0.0001, "leverage": 5.0, "risk_reward": 2.0,
}


def _build_bank(use_lancedb: bool, uri: str | None = None) -> ExperienceBank:
    bank = ExperienceBank(uri=uri, use_lancedb=use_lancedb)
    bank.from_journal(build_demo_journal())
    bank.add_many(build_extra_trades())
    return bank


_CACHE: dict | None = None


def build_demo_experience() -> dict:
    """JSON-able snapshot for the dashboard (cached). Deterministic numpy-kNN bank."""
    global _CACHE
    if _CACHE is None:
        bank = _build_bank(use_lancedb=False)
        recall = bank.recall(SAMPLE_QUERY, k=8)
        sm = SemanticMemory(enabled=False)
        sm.add("High fear-greed + high regime-confidence crypto perp LONGs tend to win.")
        sm.add("Low-conviction LONGs in a fearful tape tend to fail — wait for confirmation.")
        _CACHE = {
            "experience": bank.status(),
            "sample_recall": recall.as_dict(),
            "semantic": sm.status(),
        }
    return _CACHE


# ══════════════════════════════════════════════════════════════════════════════════
# T8.5 — continual learning + auto-quiz + meta-init + Reflexion (deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
SELFEVAL_FEATURES = ["f0", "f1", "f2", "f3"]
# A fixed linear concept: y = 1 iff a linear combo of 4 features (+noise) is positive.
# A learnable signal means a continually-learning model's accuracy should RISE with count.
_CONCEPT_W = np.array([1.6, -1.1, 0.8, -0.5])


def _learnable_stream(n: int, rng: np.random.Generator, *, weights=_CONCEPT_W,
                      noise: float = 0.45) -> list:
    """Deterministic (row, y) stream: y = sign of weights·row + gaussian noise."""
    rows = rng.normal(size=(n, len(weights)))
    logits = rows @ weights + rng.normal(scale=noise, size=n)
    ys = (logits > 0.0).astype(int)
    return list(zip(rows.tolist(), ys.tolist()))


def _concept_flip_stream(n: int, rng: np.random.Generator, *, noise: float = 0.25) -> list:
    """A stream whose concept FLIPS at the halfway point (weights negate) → drift."""
    half = n // 2
    first = _learnable_stream(half, rng, weights=_CONCEPT_W, noise=noise)
    second = _learnable_stream(n - half, rng, weights=-_CONCEPT_W, noise=noise)
    return first + second


def _trim_curve(curve: list, k: int = 15) -> list:
    """Evenly subsample a curve to ~k points (keep head→tail shape) for JSON payloads."""
    if len(curve) <= k:
        return curve
    idx = np.linspace(0, len(curve) - 1, k).round().astype(int)
    seen, out = set(), []
    for i in idx:
        if int(i) not in seen:
            seen.add(int(i))
            out.append(curve[int(i)])
    return out


_SELFEVAL_CACHE: dict | None = None


def build_demo_selfeval() -> dict:
    """JSON-able T8.5 snapshot for the dashboard (cached, deterministic, offline).

    Returns {autoquiz: QuizResult.as_dict() (curve trimmed ~15), drift_events: int,
    meta: adapt-dict (warm vs cold few-shot), reflection: self-critique note}.
    """
    global _SELFEVAL_CACHE
    if _SELFEVAL_CACHE is None:
        # (a) AutoQuiz prequential self-test on a learnable stream — proof accuracy rises.
        quiz = AutoQuiz(SELFEVAL_FEATURES, sample_every=40, warmup=20)
        qr = quiz.run(_learnable_stream(1600, np.random.default_rng(11)))

        # (b) concept-drift: OnlineNode on a stream that flips halfway.
        drift_node = OnlineNode(SELFEVAL_FEATURES, name="drift_demo")
        for row, y in _concept_flip_stream(1200, np.random.default_rng(7)):
            drift_node.learn_one(row, y)

        # (c) MAML-style warm-start few-shot benefit on a new task.
        meta = MetaLearner(SELFEVAL_FEATURES)
        mrng = np.random.default_rng(3)
        for t in range(5):
            for row, y in _learnable_stream(220, mrng):
                meta.observe(row, y, task=f"sym{t}")
        meta_res = meta.adapt(_learnable_stream(60, np.random.default_rng(99)), shots=20)

        # (d) Reflexion self-critique → semantic memory (dry-run, disabled).
        sm = SemanticMemory(enabled=False)
        by_id = {tr.trade_id: tr for tr in build_demo_journal().trades}
        a_trade = by_id.get("T3") or build_demo_journal().trades[0]
        refl = reflect_and_store(a_trade, predicted_label=1, actual_label=0,
                                 semantic_memory=sm)

        _SELFEVAL_CACHE = {
            "autoquiz": {**qr.as_dict(), "curve": _trim_curve(qr.curve, 15)},
            "drift_events": drift_node.drift_events,
            "meta": meta_res,
            "reflection": refl["note"],
        }
    return _SELFEVAL_CACHE


# ══════════════════════════════════════════════════════════════════════════════════
# T8.6 — pattern/regime discovery + asset-picking + entry/exit (deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
def _synthetic_ohlcv(seed: int = 0) -> pd.DataFrame:
    """Deterministic OHLCV with bull→bear→neutral segments + one injected price anomaly.

    Three regime segments (rising / falling / flat drift) so the HMM has distinct states
    to recover, and a single sharp spike (the injected discord) so STUMPY's matrix profile
    surfaces an anomaly the entry layer can gate on.
    """
    rng = np.random.default_rng(seed)
    seg = 120
    bull = np.linspace(0.0, 0.30, seg) + rng.normal(0, 0.004, seg)      # steady uptrend
    bear = np.linspace(0.0, -0.28, seg) + rng.normal(0, 0.004, seg)     # steady downtrend
    neutral = rng.normal(0, 0.004, seg)                                 # flat / ranging
    drift = np.concatenate([bull, bear + bull[-1], neutral + (bear[-1] + bull[-1])])
    close = 100.0 * np.exp(drift)
    # inject a sharp single-bar anomaly (discord) inside the bear segment
    close[seg + seg // 2] *= 1.18
    high = close * (1.0 + np.abs(rng.normal(0, 0.003, close.size)))
    low = close * (1.0 - np.abs(rng.normal(0, 0.003, close.size)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    vol = 1000.0 + rng.normal(0, 50, close.size)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": np.abs(vol)})


# Cross-sectional features the gplearn miner learns over; the universe carries these keys.
_PICK_FEATURES = ["mom", "vol", "ret", "rvol"]
# A hidden ground-truth factor for forward returns: reward momentum, penalise volatility.
_FACTOR_W = np.array([2.0, -1.5, 0.6, 0.4])


def _picking_training_set(seed: int = 0):
    """Synthetic cross-sectional (features → forward_return) panel for the GP miner."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(400, len(_PICK_FEATURES)))
    fwd = X @ _FACTOR_W + rng.normal(scale=0.5, size=X.shape[0])
    return X, fwd


def _demo_universe(seed: int = 0) -> dict:
    """A small symbol universe with the miner's features (deterministic)."""
    rng = np.random.default_rng(seed)
    syms = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT"]
    uni = {}
    for s in syms:
        row = rng.normal(size=len(_PICK_FEATURES))
        uni[s] = {f: round(float(v), 4) for f, v in zip(_PICK_FEATURES, row)}
    return uni


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


_BRAIN_T86_CACHE: dict | None = None


def build_demo_brain_t86() -> dict:
    """JSON-able T8.6 snapshot for the dashboard (cached, deterministic, offline).

    Returns {patterns, regime, picking:{program, top, factor_source}, entryexit}.
    """
    global _BRAIN_T86_CACHE
    if _BRAIN_T86_CACHE is None:
        ohlcv = _synthetic_ohlcv(seed=0)

        # (a) pattern + anomaly scan (STUMPY matrix profile + TA-Lib candlesticks)
        scan = PatternScanner(window=20).scan(ohlcv, k=3)
        a_score = scan["anomaly_score"]

        # (b) regime detection + regime-gated strategy activation
        reg = RegimeModel(n_states=3, seed=0).fit(ohlcv)
        current = reg.current_regime(ohlcv)
        gate = RegimeGate(allowed={
            "breakout": ("bull",), "momentum": ("bull", "neutral"),
            "mean_reversion": ("neutral", "bear"), "short_trend": ("bear",)})
        sample_strats = ["breakout", "momentum", "mean_reversion", "short_trend"]
        active = gate.activate(sample_strats, current)

        # (c) asset picking via a LEARNED VENDORED-gplearn symbolic factor
        X, fwd = _picking_training_set(seed=0)
        miner = GPLearnFactorMiner(_PICK_FEATURES, generations=8, population=400,
                                   seed=0).fit(X, fwd)
        program = miner.program()
        picker = AssetPicker(top_k=3, miner=miner)
        pick = picker.pick(_demo_universe(seed=0))

        # (d) regime/anomaly-gated entry + exit decisions
        policy = EntryExitPolicy(allowed_regimes=("bull", "neutral"), max_anomaly=3.0)
        enter = policy.should_enter(signal=1, regime=current, anomaly_score=a_score)
        exit_ = policy.should_exit(position_side="LONG", signal=-1, regime=current,
                                   anomaly_score=a_score)

        _BRAIN_T86_CACHE = _to_jsonable({
            "patterns": {
                "window": scan["window"], "engine": scan["engine"],
                "n_motifs": len(scan["motifs"]), "n_anomalies": len(scan["anomalies"]),
                "anomaly_score": a_score,
                "motifs": scan["motifs"], "anomalies": scan["anomalies"],
                "candles_firing": scan["candles_firing"],
            },
            "regime": {
                "current": current, "status": reg.status(),
                "sample_strategies": sample_strats, "active_strategies": active,
            },
            "picking": {
                "program": program, "factor_source": pick["factor_source"],
                "top": pick["top"], "ranked": pick["ranked"],
                "vendored": True, "factor_lib": "vendor/gplearn",
            },
            "entryexit": {
                "policy": policy.status(), "enter": enter, "exit": exit_,
            },
        })
    return _BRAIN_T86_CACHE


# ══════════════════════════════════════════════════════════════════════════════════
# T8.7 — autonomous news research + sentiment nodes (deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
def build_demo_news_items() -> list:
    """A FIXED offline list of NewsItems (no RSS/network) — mixed bullish/bearish for an
    NSE name (RELIANCE) and a crypto name (BTC), so per-symbol aggregation is illustrative.
    """
    return [
        NewsItem(title="Reliance Industries beats Q1 profit estimates as retail revenue surges",
                 summary="Record quarterly growth; analysts upgrade the stock to outperform.",
                 source="DemoWire", symbols=["RELIANCE"]),
        NewsItem(title="Reliance announces a large buyback and a higher dividend",
                 summary="Board approves capital return; bullish guidance for the year.",
                 source="DemoWire", symbols=["RELIANCE"]),
        NewsItem(title="Reliance shares tumble as regulator opens a probe into its telecom unit",
                 summary="Lawsuit risk and a possible fraud investigation weigh on the stock.",
                 source="DemoWire", symbols=["RELIANCE"]),
        NewsItem(title="BTC rallies to a new high as ETF inflows surge",
                 summary="Bullish momentum; institutions pile in, price set to soar.",
                 source="DemoWire", symbols=["BTC"]),
        NewsItem(title="BTC plunges after an exchange halt sparks a market-wide crash",
                 summary="Bearish cascade; leveraged longs get liquidated in a brutal slump.",
                 source="DemoWire", symbols=["BTC"]),
        NewsItem(title="BTC holds steady near support as traders await guidance",
                 summary="Range-bound session with neutral volume.",
                 source="DemoWire", symbols=["BTC"]),
    ]


_NEWS_CACHE: dict | None = None


def build_demo_news() -> dict:
    """JSON-able T8.7 snapshot for the dashboard (cached, deterministic, offline).

    Returns {scorer_backend, research:{RELIANCE:..., BTC:...}, autonomous:...,
    node_p_bullish:...}. The NewsResearcher is fed a FIXED NewsItem list (no network).
    """
    global _NEWS_CACHE
    if _NEWS_CACHE is None:
        items = build_demo_news_items()
        researcher = NewsResearcher(scorer=SentimentScorer(backend="vader"))
        rel = researcher.research("RELIANCE", items=items)
        btc = researcher.research("BTC", items=items)
        node = NewsSentimentNode()
        p_bullish = {
            "RELIANCE": round(float(node.predict_proba([[rel["avg_compound"]]])[0]), 4),
            "BTC": round(float(node.predict_proba([[btc["avg_compound"]]])[0]), 4),
        }
        autonomous = researcher.autonomous_research("RELIANCE Q1 results and outlook")
        _NEWS_CACHE = {
            "scorer_backend": researcher.scorer.active_backend,
            "research": {"RELIANCE": rel, "BTC": btc},
            "autonomous": autonomous,
            "node_p_bullish": p_bullish,
        }
    return _NEWS_CACHE


# ══════════════════════════════════════════════════════════════════════════════════
# T8.8 — skill library + observability + self-improvement (deterministic, offline)
# ══════════════════════════════════════════════════════════════════════════════════
# A labelled toy entry-gating set: CALM bars (label 1 → should ENTER) carry a small
# anomaly score; SPIKE bars (label 0 → should NOT enter) carry a large one. The optimal
# EntryExitPolicy.max_anomaly sits between the two clusters (~2.5), so hill-climbing it
# from the param-space midpoint is a REAL, measurable improvement — not a toy constant.
_ENTRY_SCENARIOS = [(0.5, 1), (1.0, 1), (1.5, 1), (2.0, 1),       # calm → enter
                    (3.0, 0), (3.5, 0), (4.0, 0), (5.0, 0), (6.0, 0)]  # spike → stay out


def _entryexit_fitness(params: dict) -> float:
    """Toy fitness over EntryExitPolicy: entry-gating accuracy + concave exit-thresh bonus.

    max_anomaly gates entries (the dominant, real term — accuracy of should_enter vs the
    labelled scenarios); exit_threshold adds a small concave reward peaking at 0.65, so
    BOTH params are genuinely optimised and the score is provably concave with a clear max.
    """
    policy = EntryExitPolicy(allowed_regimes=("bull",), max_anomaly=params["max_anomaly"],
                             exit_threshold=params["exit_threshold"])
    correct = sum(1 for a, y in _ENTRY_SCENARIOS
                  if int(policy.should_enter(signal=1, regime="bull",
                                             anomaly_score=a)["enter"]) == y)
    accuracy = correct / len(_ENTRY_SCENARIOS)
    exit_bonus = 0.1 * (1.0 - ((params["exit_threshold"] - 0.65) / 0.65) ** 2)
    return accuracy + exit_bonus


def _det_clock():
    """Deterministic monotonic clock (1.0s per call) for reproducible span timestamps."""
    t = {"v": 0.0}

    def _tick() -> float:
        t["v"] += 1.0
        return t["v"]

    return _tick


def _build_skill_library() -> tuple:
    """Build a quality-gated SkillLibrary and exercise the gate (admit/reject/improve).

    Returns (lib, events) where events is a JSON-able list of admission outcomes showing
    the gate working: real evolved strategies admitted, a losing skill rejected, an
    improvement accepted, and a worse same-named skill rejected.
    """
    from run_strategy_t8 import build_demo_population

    lib = SkillLibrary(persist=False, min_metric=0.0)
    events = []

    # (1) admit the two best evolved strategies from the T8.1/T8.2 population as skills.
    pop = build_demo_population()["population"]
    for genome_row in pop[:2]:
        res = lib.admit_strategy(genome_row["genome"], metric=genome_row["fitness_score"],
                                 metrics=genome_row["metrics"], source="evolution")
        events.append({"action": "admit_strategy", "name": genome_row["genome"].get("id"),
                       "metric": round(genome_row["fitness_score"], 4), **res})

    # (2) a losing rule fails the quality gate (metric below min_metric) → rejected.
    lossy = Skill(id="lossy", name="lossy_rule", kind="rule", market="CRYPTO",
                  payload={"rule": "buy_every_red_candle"}, metric=-0.42)
    events.append({"action": "admit(losing)", "name": lossy.name, "metric": lossy.metric,
                   **lib.admit(lossy)})

    # (3) admit a baseline rule, then IMPROVE it (higher metric, same name) → accepted.
    base = Skill(id="mom_v1", name="momentum_breakout", kind="rule", market="NSE",
                 payload={"rule": "enter_on_20d_high"}, metric=0.50)
    events.append({"action": "admit(v1)", "name": base.name, "metric": base.metric,
                   **lib.admit(base)})
    better = Skill(id="mom_v2", name="momentum_breakout", kind="rule", market="NSE",
                   payload={"rule": "enter_on_20d_high+rvol"}, metric=0.81)
    events.append({"action": "admit(v2 improved)", "name": better.name, "metric": better.metric,
                   **lib.admit(better)})

    # (4) a WORSE same-named skill is rejected (must beat the incumbent) → gate holds.
    worse = Skill(id="mom_v3", name="momentum_breakout", kind="rule", market="NSE",
                  payload={"rule": "enter_on_10d_high"}, metric=0.60)
    events.append({"action": "admit(v3 worse)", "name": worse.name, "metric": worse.metric,
                   **lib.admit(worse)})

    return lib, events


_SKILLS_CACHE: dict | None = None


def build_demo_skills() -> dict:
    """JSON-able T8.8 snapshot for the dashboard (cached, deterministic, offline).

    Returns {skills: lib.status(), stream_of_mind: [...], self_improve: {...}, dspy: {...}}.
    """
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        lib, events = _build_skill_library()

        # BrainTracer: record a sample decision's reasoning spans (deterministic clock).
        tracer = BrainTracer(clock=_det_clock())
        tracer.record("regime_check", outputs={"regime": "bull", "confidence": 0.82})
        tracer.record("news_sentiment", outputs={"symbol": "BTC", "p_bullish": 0.71})
        with tracer.trace("entry_decision", signal=1, regime="bull") as box:
            box["outputs"] = {"enter": True, "side": "LONG", "reason": "momentum + bullish news"}

        # SelfImprover: hill-climb EntryExitPolicy params against the toy fitness.
        improver = SelfImprover(n_iter=60)
        si = improver.optimize(
            {"max_anomaly": (0.5, 8.0), "exit_threshold": (0.1, 0.9)},
            _entryexit_fitness, rng=np.random.default_rng(0))

        opt = DSPyOptimizer()

        _SKILLS_CACHE = {
            "skills": lib.status(),
            "skill_events": events,
            "best": (lib.best().to_dict() if lib.best() else None),
            "stream_of_mind": tracer.stream_of_mind(10),
            "tracer": tracer.status(),
            "self_improve": {"start_score": si["start_score"], "best_score": si["best_score"],
                             "improved": si["improved"], "best_params": si["best_params"]},
            "dspy": opt.status(),
        }
    return _SKILLS_CACHE


# ══════════════════════════════════════════════════════════════════════════════════
# T8.9 — end-to-end brain trading pipeline + safety review (deterministic, offline) FINALE
# ══════════════════════════════════════════════════════════════════════════════════
def _pipeline_ohlcv(seed: int = 0) -> pd.DataFrame:
    """Deterministic OHLCV that ENDS in a clean uptrend (so the regime resolves to a
    tradeable state and the regime/anomaly entry gate can actually fire): flat → down →
    up with mild noise and NO injected discord, so the anomaly stays well under the entry
    policy's max_anomaly. One series drives both markets (paper-first, offline)."""
    rng = np.random.default_rng(seed)
    seg = 100
    flat = rng.normal(0, 0.004, seg)
    down = np.linspace(0, -0.20, seg) + rng.normal(0, 0.004, seg)
    up = np.linspace(0, 0.34, seg) + rng.normal(0, 0.004, seg)
    drift = np.concatenate([flat, down + flat[-1], up + (down[-1] + flat[-1])])
    close = 100.0 * np.exp(drift)
    high = close * (1.0 + np.abs(rng.normal(0, 0.003, close.size)))
    low = close * (1.0 - np.abs(rng.normal(0, 0.003, close.size)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    vol = 1000.0 + rng.normal(0, 50, close.size)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": np.abs(vol)})


def _pipeline_news_items(news_symbol: str) -> list:
    """The FIXED offline NewsItem feed (T8.7) narrowed to one symbol (no RSS/network)."""
    return [it for it in build_demo_news_items() if news_symbol in it.symbols]


def _new_safety() -> tuple:
    """A fresh T3 KillSwitch + DailyCircuitBreaker(persist=False) — no disk, no network."""
    ks = KillSwitch(cancel_all=lambda: {"cancelled": 0},
                    flatten_all=lambda: {"flattened": 0})
    cb = DailyCircuitBreaker(max_daily_loss=1000.0, persist=False)
    return ks, cb


def _build_pipeline(market: str, *, strat_seed: int, regime_model, news, experience,
                    kill_switch, breaker) -> BrainTradingPipeline:
    """A fully-wired BrainTradingPipeline for one market (ONE code path, both markets)."""
    strat = random_strategy(market_features(market), np.random.default_rng(strat_seed),
                            market=market, strat_id=f"{market.lower()}_evolved")
    return BrainTradingPipeline(
        market=market, evolved_strategy=strat, regime_model=regime_model, news=news,
        experience=experience, entryexit=EntryExitPolicy(), kill_switch=kill_switch,
        breaker=breaker)


_PIPELINE_CACHE: dict | None = None


def build_demo_pipeline() -> dict:
    """JSON-able T8.9 FINALE snapshot for the dashboard (cached, deterministic, offline).

    Wires a fully-injected BrainTradingPipeline for a CRYPTO and an NSE symbol off the
    SAME code path, returns each end-to-end decision (action/confidence/regime/anomaly/
    news/signal/recall bias), the crypto safety_review and Stream-of-Mind reasoning trace,
    and a SAFETY-GATE demo (engage the kill-switch → re-decide → action forced to FLAT).
    The strategy seed is chosen deterministically so the crypto decision actually fires an
    entry (non-FLAT), which makes the safety-gate demonstration meaningful.
    """
    global _PIPELINE_CACHE
    if _PIPELINE_CACHE is None:
        # shared heavy components built ONCE (regime fit + seeded experience bank).
        ohlcv = _pipeline_ohlcv()
        regime = RegimeModel(n_states=3, seed=0).fit(ohlcv)
        news = NewsResearcher(scorer=SentimentScorer(backend="vader"))
        exp = ExperienceBank(use_lancedb=False)
        exp.from_journal(build_demo_journal())
        exp.add_many(build_extra_trades())

        def decide_for(market: str, symbol: str, news_symbol: str):
            items = _pipeline_news_items(news_symbol)
            chosen = None
            for seed in range(40):       # deterministic: first seed that fires a real entry
                ks, cb = _new_safety()
                pipe = _build_pipeline(market, strat_seed=seed, regime_model=regime,
                                       news=news, experience=exp, kill_switch=ks, breaker=cb)
                d = pipe.decide(symbol, ohlcv, news_items=items)
                if chosen is None:
                    chosen = (pipe, ks, cb, seed, d)
                if d["action"] != "FLAT":
                    return pipe, ks, cb, seed, d
            return chosen

        cpipe, cks, ccb, cseed, cdec = decide_for("CRYPTO", "BTC/USDT", "BTC")
        npipe, nks, ncb, nseed, ndec = decide_for("NSE", "RELIANCE", "RELIANCE")

        # capture the clear (pre-gate) audit BEFORE engaging the safety gate.
        safety = cpipe.safety_review()
        som = cpipe.tracer.stream_of_mind(12)

        # SAFETY-GATE demo: engage the crypto kill-switch → re-decide → action == FLAT.
        cks.engage(reason="T8.9 demo kill-switch")
        cdec_blocked = cpipe.decide("BTC/USDT", ohlcv, news_items=_pipeline_news_items("BTC"))

        _PIPELINE_CACHE = _to_jsonable({
            "crypto": cdec,
            "nse": ndec,
            "safety": safety,
            "stream_of_mind": som,
            "gate_demo": {
                "before": {"action": cdec["action"],
                           "safety_blocked": cdec["safety_blocked"]},
                "after_kill_switch": {"action": cdec_blocked["action"],
                                      "safety_blocked": cdec_blocked["safety_blocked"],
                                      "safety_reason": cdec_blocked["safety_reason"]},
            },
            "strategy_seeds": {"crypto": cseed, "nse": nseed},
        })
    return _PIPELINE_CACHE


def main() -> int:
    print("ML Network Brain — Trading T8.4 (Experience Bank + Semantic Memory) offline demo")

    # ── 1. deterministic numpy-kNN experience bank ───────────────────────────────────
    bank = _build_bank(use_lancedb=False)
    _hdr("1. experience bank status (deterministic numpy-kNN store)")
    print(json.dumps(bank.status(), indent=2, default=str))

    _hdr("2. CBR recall for a NEW high-conviction setup → decision bias")
    print(f"  query setup: {SAMPLE_QUERY}")
    recall = bank.recall(SAMPLE_QUERY, k=8)
    print(f"  n_precedents={recall.n}  expected_win_rate={recall.expected_win_rate:.2f}%  "
          f"expected_pnl={recall.expected_pnl:+.4f}")
    print(f"  bias={recall.bias:+.4f} (>0 favours the trade)  "
          f"confidence={recall.confidence:.4f}")
    print("  top precedent trades (auditable):")
    for c in recall.neighbours[:5]:
        print(f"      {c['trade_id']:<7} {c['symbol']:<10} "
              f"net_pnl={c['net_pnl']:+10.2f}  win={c['win']}  "
              f"dist={c.get('_distance', 0.0):.4f}")

    # contrast: a fearful/low-conviction setup recalls the LOSE cluster
    fearful = dict(SAMPLE_QUERY, fear_greed_index=22.0, regime_confidence=27.0,
                   relative_volume=0.6, funding_rate_entry=-0.0002)
    r2 = bank.recall(fearful, k=4)
    _hdr("3. contrast — a fearful/low-conviction setup recalls the LOSE cluster")
    print(f"  expected_win_rate={r2.expected_win_rate:.2f}%  bias={r2.bias:+.4f}  "
          f"confidence={r2.confidence:.4f}  "
          f"top={[c['trade_id'] for c in r2.neighbours[:4]]}")

    # ── 4. LanceDB-backed bank (persisted) — best-effort ─────────────────────────────
    _hdr("4. LanceDB-backed experience bank (persisted to tempdir) — best-effort")
    try:
        with tempfile.TemporaryDirectory() as td:
            lbank = _build_bank(use_lancedb=True, uri=td)
            st = lbank.status()
            lr = lbank.recall(SAMPLE_QUERY, k=8)
            print(f"  store={st['store']}  n_cases={st['n_cases']}  "
                  f"recall: win_rate={lr.expected_win_rate:.2f}%  bias={lr.bias:+.4f}")
            if st["store"] != "lancedb":
                print("  (LanceDB not active — fell back to in-memory store)")
    except Exception as exc:  # pragma: no cover
        print(f"  LanceDB path skipped: {type(exc).__name__}: {str(exc)[:100]}")

    # ── 5. semantic (text) memory — mem0 dry-run ─────────────────────────────────────
    _hdr("5. semantic memory (free-text trade lessons via mem0)")
    sm = SemanticMemory(enabled=False)
    by_id = {t.trade_id: t for t in build_demo_journal().trades}
    lessons = [
        (by_id["T6"], "BTC perp LONGs in a trending tape with positive funding ran clean."),
        (by_id["T7"], "ETH perp SHORTs in a volatile chop paid funding and got squeezed."),
        (by_id["T3"], "Re-entering 2 min after a loss (revenge) on a ranging name failed."),
    ]
    for tr, lesson in lessons:
        sm.add_trade_lesson(tr, lesson)
    hits = sm.search("crypto perp long trending funding", k=3)
    print(f"  added {len(lessons)} trade lessons  backend={sm.backend}")
    if hits:
        top = hits[0]
        print(f"  search('crypto perp long trending funding') top hit:")
        print(f"      {top.get('memory', '')!r}  score={top.get('score')}  "
              f"trade_id={top.get('metadata', {}).get('trade_id')}")
    print(json.dumps(sm.status(), indent=2, default=str))
    print("  note: mem0 is installed; set MEM0_ENABLED=1 with an OpenAI-compatible "
          "key/base to activate REAL LLM-extracted semantic memory (else dry-run).")

    _hdr("6. dashboard snapshot (build_demo_experience — JSON-able, cached)")
    print(json.dumps(build_demo_experience(), indent=2, default=str)[:600] + "  ...")

    print("\n✅ T8.4 experience-bank + semantic-memory demo complete (offline, deterministic).")

    # ══════════════════════════════════════════════════════════════════════════════
    # T8.5 — continual learning + self-eval auto-quiz + meta-init + Reflexion
    # ══════════════════════════════════════════════════════════════════════════════
    print("\nML Network Brain — Trading T8.5 (Continual Learning + Self-Eval) offline demo")

    # (a) AutoQuiz prequential self-test — the headline proof accuracy RISES with count.
    _hdr("7. AutoQuiz prequential self-test (test-then-train on a learnable stream)")
    quiz = AutoQuiz(SELFEVAL_FEATURES, sample_every=40, warmup=20)
    qr = quiz.run(_learnable_stream(1600, np.random.default_rng(11)))
    print("  accuracy-vs-trade-count curve (count, rolling_accuracy):")
    head, tail = qr.curve[:4], qr.curve[-4:]
    for c in head:
        print(f"      head  count={c[0]:<5} acc={c[1]:.4f}")
    if len(qr.curve) > 8:
        print("      ...")
    for c in tail:
        print(f"      tail  count={c[0]:<5} acc={c[1]:.4f}")
    print(f"  final_accuracy={qr.final_accuracy:.4f}  slope={qr.slope:+.8f}  "
          f"rising={qr.rising}  (rising slope on a learnable stream = it gets smarter)")

    # (b) concept-drift detection — feed an OnlineNode a stream that FLIPS halfway.
    _hdr("8. concept-drift (ADWIN) — OnlineNode on a stream whose concept flips halfway")
    drift_node = OnlineNode(SELFEVAL_FEATURES, name="drift_demo")
    for row, y in _concept_flip_stream(1200, np.random.default_rng(7)):
        drift_node.learn_one(row, y)
    print(f"  n_seen={drift_node.n_seen}  drift_events={drift_node.drift_events}  "
          f"(ADWIN flags the regime shift at the halfway concept flip)")

    # (b') P&L-weighted replay (anti-catastrophic-forgetting) — exercise the buffer.
    buf = ReplayBuffer()
    rrng = np.random.default_rng(5)
    old = _learnable_stream(300, rrng)
    for row, y in old:
        buf.add(row, y, weight=abs(float(np.dot(row, _CONCEPT_W))) + 0.1)
    new = _learnable_stream(60, rrng)
    rnode = replay_retrain(SELFEVAL_FEATURES, new, buf, np.random.default_rng(5), replay_k=200)
    print(f"  replay_buffer={len(buf)} samples → replay_retrain node n_seen={rnode.n_seen} "
          f"(old regimes interleaved with new to resist forgetting)")

    # (c) MAML-style meta-init — warm-start vs cold-start few-shot accuracy + gain.
    _hdr("9. MetaLearner few-shot adapt — warm-start (cloned global) vs cold-start")
    meta = MetaLearner(SELFEVAL_FEATURES)
    mrng = np.random.default_rng(3)
    for t in range(5):
        for row, y in _learnable_stream(220, mrng):
            meta.observe(row, y, task=f"sym{t}")
    meta_res = meta.adapt(_learnable_stream(60, np.random.default_rng(99)), shots=20)
    print(f"  global_seen={meta_res['global_seen']}  shots={meta_res['shots']}")
    print(f"  warm_accuracy={meta_res['warm_accuracy']:.4f}  "
          f"cold_accuracy={meta_res['cold_accuracy']:.4f}  "
          f"few_shot_gain={meta_res['few_shot_gain']:+.4f} "
          f"(warm-started model is more sample-efficient on a new symbol)")

    # (d) Reflexion self-critique → semantic memory.
    _hdr("10. Reflexion self-critique → semantic memory (T8.4 store, dry-run)")
    sm = SemanticMemory(enabled=False)
    by_id2 = {tr.trade_id: tr for tr in build_demo_journal().trades}
    a_trade = by_id2.get("T3") or build_demo_journal().trades[0]
    refl = reflect_and_store(a_trade, predicted_label=1, actual_label=0, semantic_memory=sm)
    print(f"  self-critique note: {refl['note']!r}")
    print(f"  stored={refl['stored']}")

    _hdr("11. dashboard snapshot (build_demo_selfeval — JSON-able, cached)")
    print(json.dumps(build_demo_selfeval(), indent=2, default=str)[:700] + "  ...")

    print("\n✅ T8.5 continual-learning + self-eval demo complete (offline, deterministic).")

    # ══════════════════════════════════════════════════════════════════════════════
    # T8.6 — pattern/regime + asset-picking + entry/exit (deterministic, offline)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\nML Network Brain — Trading T8.6 (Pattern/Regime + Asset-Picking + Entry/Exit) "
          "offline demo")

    ohlcv = _synthetic_ohlcv(seed=0)

    # (a) STUMPY matrix-profile motif/anomaly discovery + TA-Lib candlesticks.
    _hdr("12. PatternScanner — STUMPY matrix-profile motifs/anomalies + TA-Lib candles")
    scan = PatternScanner(window=20).scan(ohlcv, k=3)
    print(f"  engine={scan['engine']}  window={scan['window']}  "
          f"motifs={len(scan['motifs'])}  anomalies={len(scan['anomalies'])}")
    print(f"  anomaly_score(last window vs typical)={scan['anomaly_score']:.4f}  "
          f"(injected discord at bar {120 + 60})")
    if scan["anomalies"]:
        top_a = scan["anomalies"][0]
        print(f"  biggest anomaly: index={top_a['index']}  distance={top_a['distance']:.4f}")
    print(f"  candlesticks firing on last bar: {scan['candles_firing'] or '(none)'}")

    # (b) hmmlearn GaussianHMM regime detection + RegimeGate strategy activation.
    _hdr("13. RegimeModel — hmmlearn GaussianHMM regimes + RegimeGate activation")
    reg = RegimeModel(n_states=3, seed=0).fit(ohlcv)
    current = reg.current_regime(ohlcv)
    print(f"  fitted={reg.status()['fitted']}  state→label map={reg.status()['labels']}")
    print(f"  current_regime={current!r}")
    gate = RegimeGate(allowed={
        "breakout": ("bull",), "momentum": ("bull", "neutral"),
        "mean_reversion": ("neutral", "bear"), "short_trend": ("bear",)})
    sample_strats = ["breakout", "momentum", "mean_reversion", "short_trend"]
    active = gate.activate(sample_strats, current)
    print(f"  sample strategies={sample_strats}")
    print(f"  active in {current!r} regime → {active}")

    # (c) asset-picking via a LEARNED symbolic factor from VENDORED gplearn (vendor/gplearn).
    _hdr("14. AssetPicker — LEARNED symbolic factor (VENDORED gplearn) ranks a universe")
    X, fwd = _picking_training_set(seed=0)
    miner = GPLearnFactorMiner(_PICK_FEATURES, generations=8, population=400, seed=0).fit(X, fwd)
    print(f"  features={_PICK_FEATURES}")
    print(f"  LEARNED symbolic program (from VENDORED gplearn @ vendor/gplearn):")
    print(f"      {miner.program()}")
    picker = AssetPicker(top_k=3, miner=miner)
    pick = picker.pick(_demo_universe(seed=0))
    print(f"  factor_source={pick['factor_source']!r}  (gplearn ⇒ learned factor used)")
    print(f"  top-{picker.top_k} picks: {pick['top']}")
    for r in pick["ranked"][:3]:
        print(f"      #{r['rank']} {r['symbol']:<10} score={r['score']:+.6f}")

    # (d) regime/anomaly-gated EntryExitPolicy decisions with reasons.
    _hdr("15. EntryExitPolicy — regime/anomaly-gated entry + exit decisions")
    policy = EntryExitPolicy(allowed_regimes=("bull", "neutral"), max_anomaly=3.0)
    enter = policy.should_enter(signal=1, regime=current, anomaly_score=scan["anomaly_score"])
    exit_ = policy.should_exit(position_side="LONG", signal=-1, regime=current,
                               anomaly_score=scan["anomaly_score"])
    print(f"  policy={policy.status()}")
    print(f"  should_enter(signal=+1, regime={current!r}) → {enter}")
    print(f"  should_exit(LONG, signal=-1, regime={current!r}) → {exit_}")

    _hdr("16. dashboard snapshot (build_demo_brain_t86 — JSON-able, cached)")
    print(json.dumps(build_demo_brain_t86(), indent=2, default=str)[:800] + "  ...")

    print("\n✅ T8.6 pattern/regime + asset-picking + entry/exit demo complete "
          "(offline, deterministic).")

    # ══════════════════════════════════════════════════════════════════════════════
    # T8.7 — autonomous news research + sentiment nodes (deterministic, offline)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\nML Network Brain — Trading T8.7 (Autonomous News Research + Sentiment) "
          "offline demo")

    items = build_demo_news_items()
    scorer = SentimentScorer(backend="vader")

    # (a) headline-level sentiment scoring — vendored VADER (finance-lexicon boosted).
    _hdr("17. SentimentScorer — score headlines (VENDORED VADER, finance-lexicon boosted)")
    print(f"  active_backend={scorer.active_backend!r}")
    for it in (items[0], items[2], items[3], items[4]):
        sc = scorer.score(it.text)
        print(f"      compound={sc['compound']:+.4f}  label={sc['label']:<8} "
              f"backend={sc['backend']:<6}  {it.title[:58]}")

    # (b) per-symbol NewsResearcher aggregation over the FIXED offline feed (no network).
    researcher = NewsResearcher(scorer=scorer)
    _hdr("18. NewsResearcher — per-symbol aggregated news sentiment (offline feed)")
    node = NewsSentimentNode()
    for sym in ("RELIANCE", "BTC"):
        r = researcher.research(sym, items=items)
        p = float(node.predict_proba([[r["avg_compound"]]])[0])
        top = r["top_headlines"][0]["title"] if r["top_headlines"] else "(none)"
        print(f"  {sym:<9} n={r['n_articles']}  avg_compound={r['avg_compound']:+.4f}  "
              f"label={r['label']:<8} bullish={r['bullish']} bearish={r['bearish']}  "
              f"p(bullish)={p:.4f}")
        print(f"      backend={r['backend']!r}  top headline: {top[:64]!r}")

    # (c) gated GPT-Researcher autonomous web-research hook (degrades to a note offline).
    _hdr("19. NewsResearcher.autonomous_research — gated GPT-Researcher hook")
    auto = researcher.autonomous_research("RELIANCE Q1 results and outlook")
    print(f"  available={auto['available']}  "
          f"note={auto.get('note') or auto.get('error') or '(report returned)'}")

    # (d) news → Telegram (T7) path — dry-run sentiment alert (no creds → dry-run).
    _hdr("20. news → Telegram (T7) — dry-run sentiment alert via TelegramChannel")
    rel = researcher.research("RELIANCE", items=items)
    # Force a credential-free config so this stays OFFLINE/dry-run regardless of the host
    # .env (never touch the network from the demo).
    channel = TelegramChannel(config=AlertConfig())     # no creds → dry-run, no network
    disp = AlertDispatcher([channel], deduper=Deduplicator(ttl_seconds=300.0))
    ev = signal_event(symbol="RELIANCE",
                      signal="bullish" if rel["avg_compound"] > 0 else "bearish",
                      confidence=abs(rel["avg_compound"]), source="news-sentiment")
    res = disp.dispatch(ev)                              # disabled channel → skipped (no net)
    rec = channel.send(ev)                               # honest dry-run delivery record
    print(f"  dispatched signal={ev.fields['signal']}  deduped={res['deduped']}  "
          f"channels_enabled={channel.enabled()}")
    print(f"  TelegramChannel.send → dry_run={rec['dry_run']}  ok={rec['ok']}  "
          f"detail={rec['detail']!r}")

    _hdr("21. dashboard snapshot (build_demo_news — JSON-able, cached)")
    print(json.dumps(build_demo_news(), indent=2, default=str)[:800] + "  ...")

    print("\n✅ T8.7 autonomous news research + sentiment demo complete "
          "(offline, deterministic).")

    # ══════════════════════════════════════════════════════════════════════════════
    # T8.8 — skill library + observability + self-improvement (deterministic, offline)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\nML Network Brain — Trading T8.8 (Skill Library + Observability + "
          "Self-Improvement) offline demo")

    # (a) Voyager-pattern quality-gated, growing SkillLibrary (persist=False demo).
    _hdr("22. SkillLibrary — quality-gated admission (admit / reject / improve)")
    lib, events = _build_skill_library()
    for ev in events:
        verdict = "ADMITTED" if ev.get("admitted") else "REJECTED"
        extra = (" (improved)" if ev.get("improved") else "") + (
            f"  reason={ev['reason']!r}" if ev.get("reason") else "")
        print(f"  {ev['action']:<22} {ev['name']!s:<20} metric={ev['metric']:+.4f} "
              f"→ {verdict}{extra}")
    print(f"  library status: {json.dumps(lib.status(), default=str)}")
    best = lib.best()
    print(f"  best skill: {best.name!r} (market={best.market}, metric={best.metric:.4f})"
          if best else "  best skill: (none)")

    # (b) BrainTracer — record a decision's reasoning spans → Stream-of-Mind feed.
    _hdr("23. BrainTracer — reasoning spans → Stream-of-Mind (deterministic clock)")
    tracer = BrainTracer(clock=_det_clock())
    tracer.record("regime_check", outputs={"regime": "bull", "confidence": 0.82})
    tracer.record("news_sentiment", outputs={"symbol": "BTC", "p_bullish": 0.71})
    with tracer.trace("entry_decision", signal=1, regime="bull") as box:
        box["outputs"] = {"enter": True, "side": "LONG", "reason": "momentum + bullish news"}
    print(f"  tracer backend={tracer.backend!r}  spans={tracer.status()['n_spans']}")
    print("  Stream-of-Mind:")
    for line in tracer.stream_of_mind(10):
        print(f"      • {line}")

    # (c) SelfImprover — hill-climb EntryExitPolicy params against a toy T8.2-style fitness.
    _hdr("24. SelfImprover — CPU hill-climb on EntryExitPolicy params (real, offline)")
    improver = SelfImprover(n_iter=60)
    si = improver.optimize(
        {"max_anomaly": (0.5, 8.0), "exit_threshold": (0.1, 0.9)},
        _entryexit_fitness, rng=np.random.default_rng(0))
    print(f"  start_score={si['start_score']:.4f} → best_score={si['best_score']:.4f}  "
          f"improved={si['improved']}")
    print(f"  best_params={ {k: round(v, 4) for k, v in si['best_params'].items()} }")

    # (d) DSPyOptimizer — gated LLM-program optimiser (GEPA/DSPy land here when enabled).
    _hdr("25. DSPyOptimizer — gated DSPy/GEPA LLM-program optimiser (honest status)")
    opt = DSPyOptimizer()
    print(f"  {json.dumps(opt.status(), default=str)}")
    print("  note: GEPA/DSPy activate with DSPY_ENABLED=1 + an OpenAI-compatible key "
          "(DSPY_MODEL optional); the CPU SelfImprover above works fully offline.")

    _hdr("26. dashboard snapshot (build_demo_skills — JSON-able, cached)")
    print(json.dumps(build_demo_skills(), indent=2, default=str)[:800] + "  ...")

    print("\n✅ T8.8 skill-library + observability + self-improvement demo complete "
          "(offline, deterministic).")

    # ══════════════════════════════════════════════════════════════════════════════
    # T8.9 — end-to-end brain trading pipeline + safety review (FINALE, offline)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\nML Network Brain — Trading T8.9 (End-to-End Brain Pipeline + Safety Review) "
          "offline demo — FINALE")

    snap = build_demo_pipeline()

    def _print_decision(d: dict) -> None:
        print(f"  {d['market']:<7} {d['symbol']:<10} action={d['action']:<5} "
              f"confidence={d['confidence']:.4f}")
        print(f"      regime={d['regime']!r}  anomaly_score={d['anomaly_score']:.4f}  "
              f"signal={d['signal']:+d}")
        print(f"      news_compound={d['news_compound']:+.4f} → p(bullish)={d['news_p']:.4f}  "
              f"recall_bias={d['recall_bias']:+.4f} (conf={d['recall_confidence']:.4f})")
        print(f"      entry={d['entry']}")

    # (a) CRYPTO + NSE end-to-end decisions off ONE code path.
    _hdr("27. BrainTradingPipeline — end-to-end decision (CRYPTO BTC/USDT + NSE RELIANCE)")
    _print_decision(snap["crypto"])
    _print_decision(snap["nse"])

    # (b) the crypto decision's reasoning trace (BrainTracer → Stream-of-Mind).
    _hdr("28. Stream-of-Mind — the crypto decision's traced reasoning steps")
    for line in snap["stream_of_mind"]:
        print(f"      • {line}")

    # (c) safety_review — audits the paper-first posture before any live capital.
    _hdr("29. safety_review() — paper-first safety audit (kill-switch + breaker + gates)")
    print(f"  market={snap['safety']['market']}  passed={snap['safety']['passed']}")
    for c in snap["safety"]["checks"]:
        print(f"      [{'ok ' if c['ok'] else 'WARN'}] {c['check']:<24} {c['detail']}")

    # (d) DEMONSTRATE the safety gate: engage the kill-switch → action forced to FLAT.
    _hdr("30. SAFETY GATE — engage kill-switch → re-decide → action FORCED to FLAT")
    gd = snap["gate_demo"]
    print(f"  before kill-switch: action={gd['before']['action']}  "
          f"safety_blocked={gd['before']['safety_blocked']}")
    print(f"  after  kill-switch: action={gd['after_kill_switch']['action']}  "
          f"safety_blocked={gd['after_kill_switch']['safety_blocked']}  "
          f"reason={gd['after_kill_switch']['safety_reason']!r}")
    assert gd["after_kill_switch"]["action"] == "FLAT", "safety gate failed to force FLAT"
    print("  ✔ T3 safety gate forces FLAT on kill-switch — verified.")

    _hdr("31. dashboard snapshot (build_demo_pipeline — JSON-able, cached)")
    print(json.dumps(build_demo_pipeline(), indent=2, default=str)[:800] + "  ...")

    print("\n✅ T8.9 end-to-end brain pipeline + safety review demo complete "
          "(offline, deterministic) — Phase T8 FINALE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
