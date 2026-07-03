"""Optuna-backed hyperparameter optimization (Tier-2/3 infra, group H of the model catalog).

A thin, reuse-first wrapper over Optuna (TPE sampler) for systematically tuning node
hyperparameters and arbitrary objectives — the project previously had only DEAP evolution
for search. CPU-first, no GPU. Falls back to a random search if Optuna is unavailable so
callers never break.

Typical use — tune a node's constructor kwargs against a chronological validation split:

    from core.hpo import tune_node
    best = tune_node(
        lambda **kw: RandomForestNode(**kw),
        space={"n_trees": ("int", 20, 200), "depth": ("int", 2, 8)},
        X=X, y=y, n_trials=30)
    # best -> {"params": {...}, "score": 0.63, "n_trials": 30, "backend": "optuna"}
"""
from __future__ import annotations

from typing import Callable

import numpy as np


def _suggest(trial, name: str, spec):
    """spec forms: ("int",lo,hi) | ("float",lo,hi[,"log"]) | ("cat",[choices])."""
    kind = spec[0]
    if kind == "int":
        return trial.suggest_int(name, int(spec[1]), int(spec[2]))
    if kind == "float":
        log = len(spec) > 3 and spec[3] == "log"
        return trial.suggest_float(name, float(spec[1]), float(spec[2]), log=log)
    if kind == "cat":
        return trial.suggest_categorical(name, list(spec[1]))
    raise ValueError(f"bad space spec for {name}: {spec}")


def _rand_sample(rng, spec):
    kind = spec[0]
    if kind == "int":
        return int(rng.integers(int(spec[1]), int(spec[2]) + 1))
    if kind == "float":
        return float(rng.uniform(float(spec[1]), float(spec[2])))
    if kind == "cat":
        return spec[1][int(rng.integers(0, len(spec[1])))]
    raise ValueError(spec)


def _optimize_optuna(objective, space, n_trials, direction, seed):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction=direction,
                                sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(lambda t: float(objective({k: _suggest(t, k, v) for k, v in space.items()})),
                   n_trials=n_trials, show_progress_bar=False)
    return {"params": study.best_params, "score": float(study.best_value),
            "n_trials": n_trials, "backend": "optuna"}


def _optimize_nevergrad(objective, space, n_trials, direction, seed):
    import nevergrad as ng
    params = {}
    for k, spec in space.items():
        if spec[0] == "int":
            params[k] = ng.p.Scalar(lower=spec[1], upper=spec[2]).set_integer_casting()
        elif spec[0] == "float":
            params[k] = ng.p.Scalar(lower=spec[1], upper=spec[2])
        else:
            params[k] = ng.p.Choice(list(spec[1]))
    instrum = ng.p.Instrumentation(**params)
    opt = ng.optimizers.NGOpt(parametrization=instrum, budget=n_trials)
    sign = -1.0 if direction == "maximize" else 1.0
    rec = opt.minimize(lambda **kw: sign * float(objective(kw)))
    best = {k: (int(v) if space[k][0] == "int" else v) for k, v in rec.kwargs.items()}
    return {"params": best, "score": float(sign * rec.loss), "n_trials": n_trials,
            "backend": "nevergrad"}


def _optimize_cmaes(objective, space, n_trials, direction, seed):
    # CMA-ES over continuous/int dims only (categoricals handled by rounding to index).
    import cmaes
    keys = list(space.keys())
    bounds, is_int, cats = [], [], {}
    for k in keys:
        s = space[k]
        if s[0] == "cat":
            cats[k] = list(s[1]); bounds.append((0, len(s[1]) - 1)); is_int.append(True)
        else:
            bounds.append((float(s[1]), float(s[2]))); is_int.append(s[0] == "int")
    lo = np.array([b[0] for b in bounds]); hi = np.array([b[1] for b in bounds])
    es = cmaes.CMA(mean=(lo + hi) / 2.0, sigma=float(np.mean(hi - lo)) / 4.0 + 1e-6,
                   bounds=np.array(bounds), seed=seed)
    sign = -1.0 if direction == "maximize" else 1.0
    best_p, best_s = None, np.inf
    evals = 0
    while evals < n_trials:
        sols = []
        for _ in range(es.population_size):
            x = es.ask()
            params = {}
            for i, k in enumerate(keys):
                v = x[i]
                if k in cats:
                    params[k] = cats[k][int(np.clip(round(v), 0, len(cats[k]) - 1))]
                elif is_int[i]:
                    params[k] = int(round(v))
                else:
                    params[k] = float(v)
            try:
                loss = sign * float(objective(params))
            except Exception:
                loss = np.inf
            sols.append((x, loss)); evals += 1
            if loss < best_s:
                best_s, best_p = loss, params
        es.tell(sols)
    return {"params": best_p or {}, "score": float(sign * best_s), "n_trials": evals,
            "backend": "cmaes"}


def _optimize_random(objective, space, n_trials, direction, seed):
    rng = np.random.default_rng(seed)
    best_p, best_s = None, (-np.inf if direction == "maximize" else np.inf)
    for _ in range(n_trials):
        params = {k: _rand_sample(rng, v) for k, v in space.items()}
        try:
            s = float(objective(params))
        except Exception:
            continue
        if (s > best_s) if direction == "maximize" else (s < best_s):
            best_p, best_s = params, s
    return {"params": best_p or {}, "score": float(best_s), "n_trials": n_trials,
            "backend": "random"}


_BACKENDS = {"optuna": _optimize_optuna, "nevergrad": _optimize_nevergrad,
             "cmaes": _optimize_cmaes, "random": _optimize_random}


def optimize(objective: Callable[[dict], float], space: dict, n_trials: int = 30,
             direction: str = "maximize", seed: int = 0, backend: str = "optuna") -> dict:
    """Maximize (or minimize) `objective(params)->float` over `space`.

    backend ∈ {"optuna" (TPE, default), "nevergrad" (NGOpt), "cmaes", "random"}.
    Returns {params, score, n_trials, backend}. Any backend failure (missing dep, etc.)
    falls through to random search so callers never break.
    """
    fn = _BACKENDS.get(backend, _optimize_optuna)
    try:
        return fn(objective, space, n_trials, direction, seed)
    except Exception:
        try:
            return _optimize_random(objective, space, n_trials, direction, seed)
        except Exception:
            return {"params": {}, "score": 0.0, "n_trials": 0, "backend": "failed"}


def tune_node(node_factory: Callable[..., object], space: dict, X, y,
              n_trials: int = 30, val_frac: float = 0.25, seed: int = 0,
              task: str | None = None) -> dict:
    """Tune a node's constructor kwargs on a CHRONOLOGICAL train/val split (no leakage).

    node_factory(**params) must return a NodeProtocol node. Score = validation accuracy
    (classification) or -MSE (regression, higher is better). Returns optimize()'s dict.
    """
    n = len(X)
    cut = max(10, int(n * (1.0 - val_frac)))
    Xtr, Xva = X[:cut], X[cut:]
    ytr, yva = list(y[:cut]), list(y[cut:])
    yva_arr = np.asarray(yva, float)
    is_reg = task == "regression" or (task is None and len(set(np.asarray(y).tolist())) > 3)

    def objective(params: dict) -> float:
        node = node_factory(**params)
        if task:
            node.task = task
        node.fit(Xtr, ytr)
        if is_reg:
            pred = np.asarray([r[0] for r in node.predict_output(Xva)], float)
            return -float(np.mean((pred - yva_arr) ** 2))
        preds = np.asarray(node.predict(Xva))
        return float(np.mean(preds == np.asarray(yva)))

    return optimize(objective, space, n_trials=n_trials, direction="maximize", seed=seed)
