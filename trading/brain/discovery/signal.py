"""Live discovery signal registry — feeds self-invented features into trade decisions.

Keeps a fitted ConceptDiscoveryEngine per symbol in memory. `signal(symbol, closes)` is
FAST (encode the latest window, read validated-feature activations) and NEVER blocks the
trade loop: if a symbol has no fitted engine yet or its fit is stale, a refit is kicked off
in a background thread and the current (possibly neutral) signal is returned.

Two lanes (paper-first): `validated` is proof-gated (safe to size a trade on); `experiment`
is ungated shadow (log-only). This is the wiring that turns "discovered features" into
"the brain trades on what it invents".
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .engine import ConceptDiscoveryEngine

REFIT_SEC = 1800.0                 # refit a symbol's engine at most every 30 min
_MIN_BARS = 80

_ENGINES: dict[str, ConceptDiscoveryEngine] = {}
_LAST_FIT: dict[str, float] = {}
_FITTING: set[str] = set()
_LOCK = threading.Lock()


def _fit_bg(symbol: str, closes: np.ndarray) -> None:
    try:
        eng = ConceptDiscoveryEngine(use_llm=False)
        eng.discover(series=closes)
        with _LOCK:
            _ENGINES[symbol] = eng
            _LAST_FIT[symbol] = time.time()
    except Exception:
        pass
    finally:
        with _LOCK:
            _FITTING.discard(symbol)


def signal(symbol: str, closes) -> dict:
    """Directional discovery signal for `symbol` given its recent closes.
    Returns {validated, experiment, n_val, n_exp, ready}. Non-blocking."""
    c = np.asarray(closes, float).reshape(-1)
    c = c[np.isfinite(c)]
    if len(c) < _MIN_BARS:
        return {"validated": 0.0, "experiment": 0.0, "n_val": 0, "n_exp": 0, "ready": False}

    now = time.time()
    with _LOCK:
        eng = _ENGINES.get(symbol)
        stale = (now - _LAST_FIT.get(symbol, 0.0)) > REFIT_SEC
        need_fit = (eng is None or stale) and symbol not in _FITTING
        if need_fit:
            _FITTING.add(symbol)

    if need_fit:                                     # refit in background — never block the loop
        threading.Thread(target=_fit_bg, args=(symbol, c.copy()), daemon=True).start()

    if eng is None:
        return {"validated": 0.0, "experiment": 0.0, "n_val": 0, "n_exp": 0, "ready": False}
    sig = eng.live_signal(c)
    sig["ready"] = True
    return sig


def status() -> dict:
    with _LOCK:
        return {"symbols_fitted": len(_ENGINES), "fitting": len(_FITTING),
                "last_fit": {k: round(v, 1) for k, v in _LAST_FIT.items()}}
