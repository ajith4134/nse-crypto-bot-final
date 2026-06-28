"""trading/brain/ — Brain upgrades (Phase T8.4+).

The experience→intelligence layer of the T8 blueprint. T8.4 delivers the **episodic
experience bank**: every closed trade (T5 journal) is indexed as a retrievable "case",
and Case-Based Reasoning retrieves analogous past setups to bias new decisions — so the
brain measurably improves the more it trades.

Reuse-first: the vector store is **LanceDB** (embedded, CPU, on-disk); the method is
Case-Based Reasoning over a deterministic numeric trade-vector (no LLM needed — our
trades are structured, not text). A pure-numpy fallback keeps it working offline if
LanceDB is unavailable. mem0 (LLM semantic/text memory) is an optional later add.

Pieces:
  experience — ExperienceBank: index trades, retrieve k analogous cases, recall() a
               decision bias (expected win-rate / P&L / confidence) from past outcomes
"""
from __future__ import annotations

from trading.brain.experience import (
    ExperienceBank,
    Recall,
    trade_vector,
    VEC_FIELDS,
)
from trading.brain.semantic import SemanticMemory
from trading.brain.continual import OnlineNode, ReplayBuffer, replay_retrain
from trading.brain.selfeval import AutoQuiz, QuizResult, reflect, reflect_and_store
from trading.brain.metalearn import MetaLearner
from trading.brain.patterns import (
    PatternScanner,
    anomaly_score,
    candles_firing,
    find_anomalies,
    find_motifs,
    matrix_profile,
)
from trading.brain.regime import RegimeGate, RegimeModel
from trading.brain.picking import AssetPicker, CrossSectionalRanker, GPLearnFactorMiner
from trading.brain.entryexit import EntryExitPolicy
from trading.brain.sentiment import SentimentScorer
from trading.brain.news import NewsItem, NewsResearcher, NewsSentimentNode, fetch_rss
from trading.brain.skills import Skill, SkillLibrary
from trading.brain.observability import BrainTracer, Span
from trading.brain.selfimprove import DSPyOptimizer, SelfImprover
from trading.brain.pipeline import BrainTradingPipeline

__all__ = [
    "ExperienceBank", "Recall", "trade_vector", "VEC_FIELDS", "SemanticMemory",
    "OnlineNode", "ReplayBuffer", "replay_retrain",
    "AutoQuiz", "QuizResult", "reflect", "reflect_and_store",
    "MetaLearner",
    "PatternScanner", "matrix_profile", "find_motifs", "find_anomalies",
    "anomaly_score", "candles_firing",
    "RegimeModel", "RegimeGate",
    "CrossSectionalRanker", "AssetPicker", "GPLearnFactorMiner",
    "EntryExitPolicy",
    "SentimentScorer", "NewsItem", "NewsResearcher", "NewsSentimentNode", "fetch_rss",
    "Skill", "SkillLibrary", "BrainTracer", "Span", "SelfImprover", "DSPyOptimizer",
    "BrainTradingPipeline",
]
