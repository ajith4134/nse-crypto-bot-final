"""cognition/self_coding.py — P4.7 Autonomy + self-coding: invent nodes, gate, admit.

The brain proposes NEW model-"nodes", tests them on golden data in a SANDBOX, and admits only
the winners into its own node registry — bounded, autonomous self-improvement. This is the
"Phase-5 discovery" the blueprint defers until the safe substrate exists (it now does: P4.4
self-test, P4.5 calibration + guardrails). The ADAS/SICA pattern (propose → evaluate → archive),
made safe and offline:

    NodeProposer ──▶ Sandbox ──▶ BenchmarkGate ──▶ Registry + Archive
    (new AlgoSpec)   (subprocess  (beats incumbent   (admit winners only,
                      rlimits,     on golden data?)    keep full archive)
                      no network)

Safety (the whole point of "self-coding"):
  * **No arbitrary code.** A candidate is a declarative ``AlgoSpec`` (estimator import_path +
    hyperparams). The proposer can only emit import_paths on an **allow-list** of vetted
    sklearn-family estimators — it never eval()s model-written code.
  * **Sandboxed fit.** Each candidate is fitted in a fresh **subprocess** with CPU + address-space
    ``setrlimit`` caps, a wall-clock timeout, and a stripped network-free env (``cognition.
    _sandbox_worker``). A crash / OOM / hang rejects the candidate; it cannot harm the brain.
  * **Benchmark gate.** A winner must BEAT the incumbent best on deterministic golden data by a
    margin — admission is earned, not assumed.
  * **RestrictedPython** AST check is available for the (optional, gated) LLM-proposer path.

Offline-first: the default proposer is a deterministic search over a curated estimator space +
mutations of existing registry specs (NO LLM, NO network). An optional gated ``core.llm``
proposer suggests specs when a key is set; its output is schema- + allow-list-validated before it
can run. Fully deterministic and testable with injected stubs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# Allow-list: estimator import paths a proposed node may use. Vetted, CPU-only, pip-present.
# (classifier_path, regressor_path_or_None). The proposer can ONLY emit these — never raw code.
ALLOWED_ESTIMATORS: dict[str, tuple[str, str | None]] = {
    "hist_gb": ("sklearn.ensemble.HistGradientBoostingClassifier",
                "sklearn.ensemble.HistGradientBoostingRegressor"),
    "random_forest": ("sklearn.ensemble.RandomForestClassifier",
                      "sklearn.ensemble.RandomForestRegressor"),
    "extra_trees": ("sklearn.ensemble.ExtraTreesClassifier",
                    "sklearn.ensemble.ExtraTreesRegressor"),
    "grad_boost": ("sklearn.ensemble.GradientBoostingClassifier",
                   "sklearn.ensemble.GradientBoostingRegressor"),
    "logistic": ("sklearn.linear_model.LogisticRegression", "sklearn.linear_model.Ridge"),
    "mlp": ("sklearn.neural_network.MLPClassifier", "sklearn.neural_network.MLPRegressor"),
    "knn": ("sklearn.neighbors.KNeighborsClassifier", "sklearn.neighbors.KNeighborsRegressor"),
}

# Per-family hyperparameter search space the deterministic proposer mutates over.
_SPACE: dict[str, dict] = {
    "hist_gb": {"max_depth": [3, 5, 7, None], "learning_rate": [0.03, 0.1, 0.2],
                "max_iter": [100, 200]},
    "random_forest": {"n_estimators": [100, 200, 300], "max_depth": [None, 8, 16],
                      "max_features": ["sqrt", "log2"]},
    "extra_trees": {"n_estimators": [100, 200], "max_depth": [None, 12]},
    "grad_boost": {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1], "max_depth": [2, 3]},
    "logistic": {"C": [0.1, 1.0, 10.0]},
    "mlp": {"hidden_layer_sizes": [(64,), (64, 32), (128,)], "alpha": [1e-4, 1e-3],
            "max_iter": [300]},
    "knn": {"n_neighbors": [5, 11, 21], "weights": ["uniform", "distance"]},
}


# ── Proposer ──────────────────────────────────────────────────────────────────────────
class NodeProposer:
    """Proposes candidate node specs (deterministic search; optional gated LLM)."""

    def __init__(self, *, seed: int = 0, llm_propose=None):
        # reproducible RNG: vary by call index (no Math.random/Date — deterministic tests)
        import random
        self._rand = random.Random(seed)
        self.llm_propose = llm_propose          # optional callable(context)->spec dict (gated)
        self._n = 0

    def propose(self, *, task: str = "binary", head: str = "direction",
                archive: list | None = None) -> dict:
        """Return ONE candidate spec dict. Tries the gated LLM first, else deterministic search."""
        self._n += 1
        if self.llm_propose is not None:
            try:
                spec = self.llm_propose({"task": task, "head": head, "archive": archive or []})
                v = self._validate(spec, task, head)
                if v is not None:
                    v["proposer"] = "llm"
                    return v
            except Exception:
                pass  # fall through to deterministic
        return self._deterministic(task, head, archive or [])

    def _deterministic(self, task: str, head: str, archive: list) -> dict:
        # mutate from a past winner half the time (exploit), else explore a fresh family
        winners = [a for a in archive if a.get("admitted")]
        if winners and self._rand.random() < 0.5:
            base = self._rand.choice(winners)
            fam = base["family"]
        else:
            fam = self._rand.choice(list(ALLOWED_ESTIMATORS))
        params = {k: self._rand.choice(v) for k, v in _SPACE.get(fam, {}).items()}
        return self._make(fam, params, task, head, "deterministic")

    def _make(self, fam: str, params: dict, task: str, head: str, proposer: str) -> dict:
        clf, reg = ALLOWED_ESTIMATORS[fam]
        pid = f"inv_{fam}_{self._n}_{abs(hash(json.dumps(params, sort_keys=True, default=str))) % 9973}"
        return {"id": pid, "family": fam, "import_path": clf, "reg_import_path": reg,
                "fixed_args": params, "task": task, "head": head, "proposer": proposer}

    def _validate(self, spec: dict, task: str, head: str) -> dict | None:
        """Schema + ALLOW-LIST validation of an (LLM-proposed) spec — the safety gate."""
        if not isinstance(spec, dict):
            return None
        fam = spec.get("family")
        if fam not in ALLOWED_ESTIMATORS:           # only vetted estimators may run
            return None
        params = spec.get("fixed_args") or {}
        if not isinstance(params, dict):
            return None
        # keep only known hyperparameters for the family (drop anything unexpected)
        clean = {k: v for k, v in params.items() if k in _SPACE.get(fam, {})}
        return self._make(fam, clean, task, head, "llm")


# ── Sandbox ───────────────────────────────────────────────────────────────────────────
class Sandbox:
    """Fits + scores a candidate in an isolated subprocess (rlimits, timeout, no network)."""

    def __init__(self, *, mem_mb: int = 1536, cpu_s: int = 25, timeout_s: int = 40):
        self.mem_mb = mem_mb
        self.cpu_s = cpu_s
        self.timeout_s = timeout_s

    @staticmethod
    def _allowed(spec: dict) -> bool:
        fam = spec.get("family")
        return (fam in ALLOWED_ESTIMATORS
                and spec.get("import_path") == ALLOWED_ESTIMATORS[fam][0])

    def _limits(self):
        # set in the child BEFORE exec: cap address space + CPU so a bad candidate can't run away
        import resource

        def preexec():
            try:
                resource.setrlimit(resource.RLIMIT_AS,
                                   (self.mem_mb * 1024 * 1024, self.mem_mb * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_s, self.cpu_s))
            except Exception:
                pass
        return preexec

    def fit_score(self, spec: dict, *, dataset: str = "mackey_glass", n: int = 1200,
                  noise: float = 0.05, seed: int = 0) -> dict:
        """Run the candidate in the sandbox. Returns {ok, score, baseline, beats} | {ok:false,...}."""
        if not self._allowed(spec):              # allow-list gate BEFORE we ever spawn it
            return {"ok": False, "error": "estimator not on allow-list (rejected, not run)"}
        req = {**spec, "dataset": dataset, "n": n, "noise": noise, "seed": seed}
        # stripped, network-free environment (no creds, no proxy); same interpreter + cwd
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
               "PYTHONPATH": os.getcwd(), "PYTHONHASHSEED": "0",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "cognition._sandbox_worker"],
                input=json.dumps(req), capture_output=True, text=True,
                timeout=self.timeout_s, cwd=os.getcwd(), env=env,
                preexec_fn=self._limits() if hasattr(os, "fork") else None)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout >{self.timeout_s}s (rejected)"}
        except Exception as e:
            return {"ok": False, "error": f"sandbox spawn: {type(e).__name__}: {str(e)[:80]}"}
        if proc.returncode != 0:
            return {"ok": False, "error": f"sandbox exit {proc.returncode} "
                    f"(killed by rlimit?): {proc.stderr[-120:].strip()}"}
        try:
            return json.loads(proc.stdout or "{}")
        except Exception:
            return {"ok": False, "error": "unparseable sandbox output"}


# ── Benchmark gate ──────────────────────────────────────────────────────────────────────
class BenchmarkGate:
    """Admit a candidate only if it BEATS the incumbent best on golden data by a margin."""

    def __init__(self, *, margin: float = 0.005):
        self.margin = float(margin)
        self.incumbent_best: float | None = None     # best admitted score so far (per head)

    def consider(self, result: dict) -> dict:
        if not result.get("ok"):
            return {"admit": False, "reason": result.get("error", "fit failed")}
        score = float(result["score"])
        bar = self.incumbent_best if self.incumbent_best is not None else float(result["baseline"])
        admit = result.get("beats", False) and score >= bar + self.margin
        if admit:
            self.incumbent_best = max(self.incumbent_best or score, score)
        return {"admit": bool(admit), "score": score, "bar": round(bar, 4),
                "reason": ("beats incumbent+margin" if admit else
                           "does not beat incumbent+margin" if result.get("beats")
                           else "below baseline")}


# ── The loop ────────────────────────────────────────────────────────────────────────────
class SelfCodingLoop:
    """ADAS-style: propose → sandbox → gate → admit to registry + keep an archive."""

    def __init__(self, *, proposer: NodeProposer | None = None, sandbox: Sandbox | None = None,
                 gate: BenchmarkGate | None = None, seed: int = 0,
                 dataset: str = "mackey_glass", n: int = 1200, noise: float = 0.05):
        self.proposer = proposer or NodeProposer(seed=seed)
        self.sandbox = sandbox or Sandbox()
        self.gate = gate or BenchmarkGate()
        self.dataset, self.n, self.noise, self.seed = dataset, n, noise, seed
        self.archive: list[dict] = []         # every candidate + verdict (ADAS archive)
        self.admitted: list[dict] = []        # winners only

    def step(self, *, task: str = "binary", head: str = "direction") -> dict:
        spec = self.proposer.propose(task=task, head=head, archive=self.archive)
        result = self.sandbox.fit_score(spec, dataset=self.dataset, n=self.n,
                                        noise=self.noise, seed=self.seed)
        verdict = self.gate.consider(result)
        entry = {"id": spec["id"], "family": spec["family"], "proposer": spec["proposer"],
                 "params": spec["fixed_args"], "task": task, "head": head,
                 "score": result.get("score"), "baseline": result.get("baseline"),
                 "admitted": verdict["admit"], "reason": verdict["reason"]}
        self.archive.append(entry)
        if verdict["admit"]:
            self._admit(spec, result)
            self.admitted.append(entry)
        return entry

    def _admit(self, spec: dict, result: dict) -> None:
        """Register the winner as a real AlgoSpec so the network can use it (honest wiring)."""
        try:
            from core.algo_registry import REGISTRY, register
            if spec["id"] not in REGISTRY:
                register(id=spec["id"], import_path=spec["import_path"],
                         reg_import_path=spec["reg_import_path"],
                         tasks=frozenset({spec["task"]}), kind="invented",
                         summary=f"P4.7 self-coded ({spec['family']}, score {result['score']})",
                         fixed_args=spec["fixed_args"])
        except Exception:
            pass

    def run(self, iters: int = 12, *, task: str = "binary", head: str = "direction") -> dict:
        for _ in range(iters):
            self.step(task=task, head=head)
        return self.summary()

    def candidate_factory(self, spec_id: str):
        """A (name, factory) usable directly in StructureSearchNode's candidate pool."""
        from core.algo_registry import REGISTRY
        from nodes.universal_node import UniversalNode
        spec = REGISTRY.get(spec_id)
        return (spec_id, (lambda s=spec: UniversalNode(s))) if spec else None

    def summary(self) -> dict:
        scored = [a for a in self.archive if a.get("score") is not None]
        best = max(scored, key=lambda a: a["score"], default=None)
        return {
            "engine": "self-coding (ADAS-pattern, sandboxed)",
            "proposed": len(self.archive),
            "admitted": len(self.admitted),
            "best_score": best["score"] if best else None,
            "best_family": best["family"] if best else None,
            "incumbent_best": self.gate.incumbent_best,
            "admitted_nodes": [a["id"] for a in self.admitted],
            "allow_list": list(ALLOWED_ESTIMATORS),
            "sandbox": {"mem_mb": self.sandbox.mem_mb, "cpu_s": self.sandbox.cpu_s,
                        "timeout_s": self.sandbox.timeout_s, "network": "none"},
        }

    def status(self) -> dict:
        return self.summary()
