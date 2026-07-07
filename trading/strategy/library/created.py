"""trading/strategy/library/created.py — brain-CREATED strategies as first-class library entries.

Closes the strategy-creator loop. The foundry, the 6 generators (symbolic / alpha-mining /
llm-mutation / quality-diversity / optuna / rd-agent) and the DEAP genetic evolution all admit
their CPCV+DSR+guardrail-PASSED survivors into ONE persisted store — the `SkillLibrary`
(`trading.brain.skills`). Until now the LIVE executor only ever saw the STATIC institutional
catalog: the real crypto path is

    broker-sense funnel → BrainExecutor → PerCoinBrainDecider → LibraryBrainDecider.strategies()
        = trading.strategy.library.registry.get_registry().executable()   ← static catalog only

so brain-created strategies (which land in the SkillLibrary) never entered the choice set and could
never win a real trade — a WIRING gap, not a capability gap (see research/strategy-creator-to-brain.md).

This module reads the admitted skills and wraps each reconstructable, executable candidate as a
`LibraryStrategy`. The signal is the candidate's own `.signal`, GUARDED so that if the live feed is
missing any feature the strategy needs (e.g. `ema` is in FEATURE_NAMES but not EXT_FEATURE_NAMES) it
returns FLAT (0) instead of raising — honest degradation, never a fabricated signal. `registry`
merges these, so `executable()` now includes them and the per-coin decider ranks brain-created
strategies alongside the institutional library. The unique skill id becomes the strategy name →
Freqtrade `enter_tag` → visible per-coin on both dashboards; the ledger's promote/prune then keeps
only the created strategies that actually stay profitable.

Reuse-first: reconstruction uses the canonical `generators.base.rebuild` (the same `__type__`
dispatch `evolved_link` uses), so genome / expression / any future candidate type all work with no
per-shape parsing here.
"""
from __future__ import annotations

import os

import pandas as pd

from trading.strategy.library.base import DataReq, LibraryStrategy

# skill market tag → library segments it should compete in.
_MARKET_SEGMENTS = {
    "CRYPTO": ("crypto_futures", "crypto_spot"),
    "NSE": ("nse_intraday", "nse_futures"),
}
_DEFAULT_SEGMENTS = ("crypto_futures",)


def _segments_for(market: str) -> tuple:
    return _MARKET_SEGMENTS.get((market or "").upper(), _DEFAULT_SEGMENTS)


def _guarded_signal(candidate):
    """Wrap `candidate.signal` so a feature the live feed lacks → FLAT (0), never a crash.

    Created strategies are built over FEATURE_NAMES; the executor feeds EXT_FEATURE_NAMES. Any
    strategy needing a column absent from the incoming frame (or that errors) goes flat — it simply
    won't be chosen, which is the honest outcome (no signal fabricated)."""
    needed = list(getattr(candidate, "features", []) or [])

    def _sig(ext_feats: pd.DataFrame) -> pd.Series:
        if any(f not in ext_feats.columns for f in needed):
            return pd.Series(0, index=ext_feats.index, dtype=int)
        try:
            return candidate.signal(ext_feats)
        except Exception:
            return pd.Series(0, index=ext_feats.index, dtype=int)

    return _sig


def load_created_strategies(*, min_metric: float | None = None,
                            state_file: str = "skill_library.json") -> list[LibraryStrategy]:
    """Read admitted, gated brain-created skills and wrap each as an executable LibraryStrategy.

    Best-effort: returns [] on any failure (missing deps, empty store) — never raises into the
    registry build. `min_metric` defaults to env CREATED_MIN_METRIC (default 0.0 = the SkillLibrary
    admission gate; raise it to be stricter about which created strategies reach live trading)."""
    try:
        from trading.brain.skills import SkillLibrary
        from trading.strategy.generators.base import rebuild
        import trading.strategy.generators  # noqa: F401 — registers non-genome __type__ handlers
    except Exception:
        return []

    if min_metric is None:
        try:
            min_metric = float(os.environ.get("CREATED_MIN_METRIC", "0") or 0)
        except Exception:
            min_metric = 0.0

    try:
        lib = SkillLibrary(state_file=state_file)
    except Exception:
        return []

    out: list[LibraryStrategy] = []
    for skill in lib.retrieve(k=100_000):
        if getattr(skill, "kind", "") != "strategy" or not skill.payload:
            continue
        try:
            metric = float(getattr(skill, "metric", 0.0) or 0.0)
        except Exception:
            metric = 0.0
        if metric < min_metric:
            continue
        cand = rebuild(skill.payload)
        if cand is None or not hasattr(cand, "signal"):
            continue
        out.append(LibraryStrategy(
            name=skill.name,
            category="machine_learning",
            family=f"created:{skill.source or 'evolution'}",
            logic=(f"Brain-created strategy ({skill.source or 'evolution'}), "
                   f"OOS metric {metric:.3f}"),
            segments=_segments_for(getattr(cand, "market", skill.market)),
            timeframe="intraday 5m",
            data_req=(DataReq.OHLCV, DataReq.VOLUME),
            signal=_guarded_signal(cand),
            oss_source=skill.source or "",
            params={"metric": round(metric, 4), **(skill.metrics or {})},
            allow_short=bool(skill.payload.get("allow_short", True)),
            notes=f"created:{skill.source}; id={skill.name}; generation={skill.generation}",
        ))
    return out


def created_store_signature(state_file: str = "skill_library.json"):
    """Cheap change-token (mtime, size) for the persisted created-strategy store, or None.

    Lets the registry auto-rebuild when a new strategy is admitted mid-run — closing the loop LIVE
    without a restart — while keeping the static catalog cached. Reads STATE_DIR at call time so the
    test-isolation monkeypatch (trading.state.STATE_DIR) is honoured."""
    try:
        from trading import state
        st = (state.STATE_DIR / state_file).stat()
        return (st.st_mtime, st.st_size)
    except Exception:
        return None


# NB: intentionally NO module-level `STRATEGIES = load_created_strategies()`. The registry calls
# load_created_strategies() FRESH on each (re)build, so an eager import-time snapshot would (a) do
# file I/O + import the generators at import time and (b) read the live STATE_DIR before any test
# monkeypatch — a non-isolation footgun. Consumers call the function.
