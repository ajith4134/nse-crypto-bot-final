"""trading/brain/hypothesis.py — the brain's hypothesis → experiment → belief loop.

Upgrades the PARTIAL "hypothesis→experiment" capability (research/brain-stitch-gap-map.md)
into a formal AI-Scientist / RD-Agent style research loop, CPU-first and reuse-first:

  propose  -> read the closed-trade journal and emit testable hypotheses
              ("LONG trades in a Trending regime beat the rest on R")
  test     -> run an EXPERIMENT measuring the claim two ways:
                journal backend     — split real closed trades condition-vs-control,
                                      Bayesian Beta-Binomial A/B on win-rate (numpy MC)
                                      + Welch t-test on R-multiple (scipy.stats)
                imagination backend — counterfactual: roll the world-model planner
                                      (trading/brain/worldmodel.py) forward and compare
                                      imagined_R of two actions
  update   -> Bayesian credence in [0,1]; status open / confirmed / refuted
  reflect  -> confirmed -> insight notes (optionally into SemanticMemory);
              refuted   -> a FAILURE database (the chat's "Failure Notes")

Persisted via trading.state (load_json/save_json), so the ledger compounds across
sessions. A HypothesisNode exposes the learned base credence on the NodeProtocol so the
capability appears in the node registry + dashboard.

Inputs:  closed-trade dicts (journal) and/or an ImaginationPlanner.
Outputs: a persisted ledger of credenced hypotheses + reflections (dicts).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

import numpy as np

from core.node_protocol import BaseNode, IOSchema

try:
    from scipy import stats as _sps
    _HAS_SCIPY = True
except Exception:                       # pragma: no cover
    _HAS_SCIPY = False

CONFIRM_AT = 0.80       # credence ≥ -> confirmed
REFUTE_AT = 0.20        # credence ≤ -> refuted
MIN_EVIDENCE = 8        # need at least this many condition-group trades to rule


# ============================================================================ #
#  Hypothesis                                                                   #
# ============================================================================ #
@dataclass
class Hypothesis:
    """A testable claim: trades where <field op value> beat the rest on <metric>."""
    field: str                       # trade key, e.g. "market_regime_entry"
    op: str                          # "==", ">", "<", "in"
    value: object                    # threshold / category / list
    metric: str = "r_multiple"       # "r_multiple" | "win" | "net_pnl"
    statement: str = ""
    # belief / evidence
    credence: float = 0.5            # P(condition better than control)
    status: str = "open"             # open | confirmed | refuted
    n_cond: int = 0
    n_ctrl: int = 0
    effect_size: float = 0.0         # mean(metric|cond) - mean(metric|ctrl)
    p_value: float = 1.0
    win_rate_cond: float = 0.0
    win_rate_ctrl: float = 0.0
    source: str = "journal"          # which experiment backend produced the evidence
    hid: str = ""

    def __post_init__(self):
        if not self.statement:
            self.statement = (f"trades where {self.field} {self.op} {self.value!r} "
                              f"beat the rest on {self.metric}")
        if not self.hid:
            key = f"{self.field}|{self.op}|{self.value}|{self.metric}"
            self.hid = hashlib.sha1(key.encode()).hexdigest()[:10]

    # ---- the predicate ----------------------------------------------------
    def holds(self, trade: dict) -> bool:
        v = trade.get(self.field)
        if v is None or v == "":
            return False
        try:
            if self.op == "==":
                return str(v) == str(self.value)
            if self.op == "in":
                return v in self.value
            fv, tv = float(v), float(self.value)
            return fv > tv if self.op == ">" else fv < tv
        except (TypeError, ValueError):
            return False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        keep = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**keep)


# ============================================================================ #
#  ExperimentRunner — measures a hypothesis (real + counterfactual)             #
# ============================================================================ #
def _metric_values(trades: list[dict], metric: str) -> np.ndarray:
    out = []
    for t in trades:
        v = t.get(metric)
        if v is None and metric == "r_multiple":
            v = t.get("net_pnl")            # fall back to P&L sign if no R recorded
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return np.asarray(out, dtype=float)


def _win_rate(vals: np.ndarray) -> float:
    return float((vals > 0).mean()) if len(vals) else 0.0


def _bayes_ab(cond: np.ndarray, ctrl: np.ndarray, draws: int = 4000,
              seed: int = 0) -> float:
    """P(win-rate(cond) > win-rate(ctrl)) via Beta-Binomial posteriors (numpy MC)."""
    rng = np.random.default_rng(seed)
    cw, cl = float((cond > 0).sum()), float((cond <= 0).sum())
    kw, kl = float((ctrl > 0).sum()), float((ctrl <= 0).sum())
    pc = rng.beta(1 + cw, 1 + cl, draws)
    pk = rng.beta(1 + kw, 1 + kl, draws)
    return float((pc > pk).mean())


class ExperimentRunner:
    """Runs the experiment behind a hypothesis and returns an evidence dict."""

    def from_journal(self, hyp: Hypothesis, trades: list[dict], seed: int = 0) -> dict:
        cond = [t for t in trades if hyp.holds(t)]
        ctrl = [t for t in trades if not hyp.holds(t)]
        cv = _metric_values(cond, hyp.metric)
        kv = _metric_values(ctrl, hyp.metric)
        if len(cv) < 1 or len(kv) < 1:
            return {"n_cond": len(cv), "n_ctrl": len(kv), "credence": 0.5,
                    "effect_size": 0.0, "p_value": 1.0, "win_rate_cond": _win_rate(cv),
                    "win_rate_ctrl": _win_rate(kv), "source": "journal"}
        credence = _bayes_ab(cv, kv, seed=seed)
        effect = float(cv.mean() - kv.mean())
        if _HAS_SCIPY and len(cv) > 1 and len(kv) > 1:
            p = float(_sps.ttest_ind(cv, kv, equal_var=False).pvalue)
        else:
            p = 1.0
        return {"n_cond": len(cv), "n_ctrl": len(kv), "credence": credence,
                "effect_size": effect, "p_value": p, "win_rate_cond": _win_rate(cv),
                "win_rate_ctrl": _win_rate(kv), "source": "journal"}

    def from_imagination(self, planner, states: list, action_a: str, action_b: str,
                         seed: int = 0) -> dict:
        """Counterfactual experiment: compare imagined_R of action_a vs action_b.

        `states` = list of OHLCV frames (sampled market situations). Returns the same
        evidence shape; "win" = action_a imagined better than action_b at that state.
        """
        ra, rb = [], []
        for df in states:
            try:
                plan = planner.plan(df)
                ra.append(float(plan["imagined_R"].get(action_a, 0.0)))
                rb.append(float(plan["imagined_R"].get(action_b, 0.0)))
            except Exception:
                continue
        a, b = np.asarray(ra), np.asarray(rb)
        if len(a) < 1:
            return {"n_cond": 0, "n_ctrl": 0, "credence": 0.5, "effect_size": 0.0,
                    "p_value": 1.0, "win_rate_cond": 0.0, "win_rate_ctrl": 0.0,
                    "source": "imagination"}
        diff = a - b
        credence = float((diff > 0).mean())
        p = float(_sps.ttest_rel(a, b).pvalue) if _HAS_SCIPY and len(a) > 1 else 1.0
        return {"n_cond": len(a), "n_ctrl": len(b), "credence": credence,
                "effect_size": float(diff.mean()), "p_value": p,
                "win_rate_cond": _win_rate(a), "win_rate_ctrl": _win_rate(b),
                "source": "imagination"}


# ============================================================================ #
#  HypothesisLedger — propose / test / reflect / persist                        #
# ============================================================================ #
class HypothesisLedger:
    """The brain's notebook of credenced, evidence-backed trading hypotheses."""

    STATE_FILE = "hypotheses.json"

    def __init__(self, *, persist: bool = True, semantic_memory=None):
        self.persist = persist
        self.semantic = semantic_memory             # optional SemanticMemory sink
        self.runner = ExperimentRunner()
        self.hypotheses: dict[str, Hypothesis] = {}
        self.failures: list[dict] = []              # the "Failure Notes" database
        self._load()

    # ---- persistence ------------------------------------------------------
    def _load(self):
        if not self.persist:
            return
        from trading import state
        blob = state.load_json(self.STATE_FILE, {})
        for d in blob.get("hypotheses", []):
            h = Hypothesis.from_dict(d)
            self.hypotheses[h.hid] = h
        self.failures = blob.get("failures", [])

    def _save(self):
        if not self.persist:
            return
        from trading import state
        state.save_json(self.STATE_FILE, {
            "hypotheses": [h.to_dict() for h in self.hypotheses.values()],
            "failures": self.failures,
        })

    # ---- propose ----------------------------------------------------------
    def propose(self, trades: list[dict]) -> list[Hypothesis]:
        """Read the journal and emit candidate hypotheses over observed structure."""
        proposals: list[Hypothesis] = []

        def add(field_, op, value, metric="r_multiple"):
            h = Hypothesis(field=field_, op=op, value=value, metric=metric)
            if h.hid not in self.hypotheses:
                proposals.append(h)

        # categorical fields present in the data -> one hypothesis per category
        for field_ in ("market_regime_entry", "direction", "strategy_name", "market"):
            cats = {str(t.get(field_)) for t in trades if t.get(field_)}
            for c in sorted(cats):
                add(field_, "==", c)
        # numeric threshold fields -> high-vs-rest hypotheses at the median
        for field_ in ("brain_confidence_entry", "regime_confidence", "entry_hour"):
            vals = _metric_values([{field_: t.get(field_)} for t in trades
                                   if t.get(field_) is not None], field_)
            if len(vals) >= MIN_EVIDENCE:
                add(field_, ">", round(float(np.median(vals)), 4))
        for h in proposals:
            self.hypotheses[h.hid] = h
        self._save()
        return proposals

    # ---- test -------------------------------------------------------------
    def test(self, hyp: Hypothesis, trades: list[dict], seed: int = 0) -> Hypothesis:
        ev = self.runner.from_journal(hyp, trades, seed=seed)
        hyp.n_cond, hyp.n_ctrl = ev["n_cond"], ev["n_ctrl"]
        hyp.credence = round(ev["credence"], 4)
        hyp.effect_size = round(ev["effect_size"], 6)
        hyp.p_value = round(ev["p_value"], 6)
        hyp.win_rate_cond = round(ev["win_rate_cond"], 4)
        hyp.win_rate_ctrl = round(ev["win_rate_ctrl"], 4)
        hyp.source = ev["source"]
        hyp.status = self._verdict(hyp)
        self.hypotheses[hyp.hid] = hyp
        return hyp

    def _verdict(self, hyp: Hypothesis) -> str:
        if hyp.n_cond < MIN_EVIDENCE:
            return "open"
        if hyp.credence >= CONFIRM_AT and hyp.effect_size > 0:
            return "confirmed"
        if hyp.credence <= REFUTE_AT or (hyp.effect_size < 0 and hyp.credence < 0.5):
            return "refuted"
        return "open"

    # ---- reflect ----------------------------------------------------------
    def reflect(self) -> dict:
        """Promote confirmed -> notes; archive refuted -> failure DB."""
        insights, failures_new = [], []
        for h in self.hypotheses.values():
            if h.status == "confirmed":
                note = (f"[confirmed p={h.credence:.2f}, +{h.effect_size:.3f}{h.metric}] "
                        f"{h.statement}")
                insights.append(note)
                if self.semantic is not None:
                    try:
                        self.semantic.add(note)
                    except Exception:
                        pass
            elif h.status == "refuted":
                fail = {"hid": h.hid, "statement": h.statement, "credence": h.credence,
                        "effect_size": h.effect_size}
                if not any(f["hid"] == h.hid for f in self.failures):
                    self.failures.append(fail)
                    failures_new.append(fail)
        self._save()
        return {"insights": insights, "new_failures": failures_new}

    # ---- the full research cycle -----------------------------------------
    def run_cycle(self, trades: list[dict], seed: int = 0) -> dict:
        """propose -> test all open/known -> reflect -> persist. Returns a summary."""
        self.propose(trades)
        for h in list(self.hypotheses.values()):
            if h.status != "refuted":           # keep re-testing open/confirmed as data grows
                self.test(h, trades, seed=seed)
        refl = self.reflect()
        return {"n_hypotheses": len(self.hypotheses), **self.counts(),
                "insights": refl["insights"], "failures": len(self.failures)}

    # ---- consult (for the pipeline) --------------------------------------
    def support(self, context: dict) -> dict:
        """Aggregate credence/effect from CONFIRMED hypotheses matching `context`.

        `context` is a trade-like dict (regime/direction/...). Returns a bias in
        [-1, 1] and the matching statements, so the pipeline can weight a decision.
        """
        matched = [h for h in self.hypotheses.values()
                   if h.status == "confirmed" and h.holds(context)]
        if not matched:
            return {"bias": 0.0, "n": 0, "statements": []}
        bias = float(np.tanh(np.mean([h.effect_size for h in matched]) * 2.0))
        return {"bias": round(bias, 4), "n": len(matched),
                "statements": [h.statement for h in matched[:5]]}

    # ---- views ------------------------------------------------------------
    def counts(self) -> dict:
        st = [h.status for h in self.hypotheses.values()]
        return {"confirmed": st.count("confirmed"), "refuted": st.count("refuted"),
                "open": st.count("open")}

    def top(self, k: int = 12) -> list[dict]:
        ranked = sorted(self.hypotheses.values(),
                        key=lambda h: (h.status == "confirmed", h.credence), reverse=True)
        return [h.to_dict() for h in ranked[:k]]

    def to_json(self) -> dict:
        return {**self.counts(), "n_hypotheses": len(self.hypotheses),
                "top": self.top(), "failures": self.failures[-10:]}


# ============================================================================ #
#  HypothesisNode — NodeProtocol face                                           #
# ============================================================================ #
class HypothesisNode(BaseNode):
    """NodeProtocol face: predict_proba = the brain's confirmed base win-credence.

    fit(X, y) records the base win-rate from labels; predict_proba blends it with the
    mean credence of confirmed hypotheses, so the node reflects learned belief. Keeps
    the research capability visible in the registry/dashboard (dashboard-sync).
    """
    name = "hypothesis_ledger"
    kind = "research"
    summary = "AI-Scientist loop: propose→experiment→Bayesian-credence→confirm/refute trading hypotheses"
    schema = IOSchema(1, "decision context", "p(positive outcome | confirmed hypotheses)")
    task = "binary"
    head = "y"

    def __init__(self, ledger: HypothesisLedger | None = None):
        self.ledger = ledger or HypothesisLedger(persist=False)
        self._base = 0.5

    def fit(self, X, y):
        ya = np.asarray(y, dtype=float)
        if len(ya):
            self._base = float((ya > 0).mean())
        return self

    def predict_proba(self, X):
        conf = [h.credence for h in self.ledger.hypotheses.values()
                if h.status == "confirmed"]
        cred = float(np.mean(conf)) if conf else 0.5
        p = max(0.0, min(1.0, 0.5 * self._base + 0.5 * cred))
        n = len(X) if hasattr(X, "__len__") else 1
        return [p] * n


def register_hypothesis_ledger(ledger: HypothesisLedger | None = None) -> HypothesisNode:
    """Self-register on the live node registry (dashboard-sync). Idempotent."""
    from core import registry
    node = HypothesisNode(ledger=ledger)
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
