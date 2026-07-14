"""trading/direction/river_source.py — River online learner as a measured direction source.

A drift-aware River model (StandardScaler → LogisticRegression) that predicts P(price up) from
the SAME ``{m_<name>: p_up}`` feature dict the direction_model (proposal B) uses — so there is no
train/serve skew. It is bootstrapped once from the closed-trade journal (each trade's decision
snapshot gives the features; its realized outcome gives the label ``up = (direction==LONG) ==
(net_pnl>0)``), then keeps learning online as trades close.

Exposed to :mod:`trading.direction.brain_sources` as the ``river_online`` source. Like every
other lens it is fused by measured edge on the Truth Ledger, so it starts weightless and earns
the right to move trades only once it proves right (River adapts faster than the batch model, so
its value is fast concept-drift adaptation). All CPU, deterministic, persisted via trading.state.
"""
from __future__ import annotations

import pickle
import threading
import time

_LOCK = threading.RLock()
_STATE_FILE = "river_source.pkl"
_MIN_TRAIN = 50                     # samples before predict() is trusted (else abstain → None)
_PERSIST_EVERY = 25                 # online updates between disk writes
_MODEL = None                       # {"model", "n", "since_save"}
_BOOTSTRAPPED = False


def _new_model():
    from river import compose, linear_model, preprocessing
    return compose.Pipeline(preprocessing.StandardScaler(), linear_model.LogisticRegression())


def _state_path():
    from trading import state
    return state._path(_STATE_FILE) if hasattr(state, "_path") else None


def _load() -> dict:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            p = _state_path()
            with open(p, "rb") as f:
                blob = pickle.load(f)
            _MODEL = {"model": blob["model"], "n": int(blob.get("n", 0)), "since_save": 0}
        except Exception:
            _MODEL = {"model": _new_model(), "n": 0, "since_save": 0}
    return _MODEL


def _save() -> None:
    try:
        p = _state_path()
        if not p:
            return
        with _LOCK:
            with open(p, "wb") as f:
                pickle.dump({"model": _MODEL["model"], "n": _MODEL["n"],
                             "ts": time.time()}, f)
            _MODEL["since_save"] = 0
    except Exception:
        pass


def _features_from_filters(filters: dict) -> dict:
    """Map a journal snapshot's ``{'filter:funding': p, ...}`` to the live ``{m_funding: p}``
    convention (identical to app_signals.feature_dict) so bootstrap == serve features."""
    out = {}
    for k, v in (filters or {}).items():
        try:
            out["m_" + str(k).split(":", 1)[-1]] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _clean(features: dict) -> dict:
    out = {}
    for k, v in (features or {}).items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == fv:                                  # drop NaN
            out[str(k)] = fv
    return out


def learn(features: dict, up: bool) -> None:
    """Online update from one realized outcome. Safe to call from the trade-close path."""
    x = _clean(features)
    if not x:
        return
    with _LOCK:
        m = _load()
        try:
            m["model"].learn_one(x, bool(up))
            m["n"] += 1
            m["since_save"] += 1
        except Exception:
            return
        due = m["since_save"] >= _PERSIST_EVERY
    if due:
        _save()


def predict(features: dict) -> float | None:
    """P(up) in [0,1] once the model has seen >= _MIN_TRAIN samples; else None (abstain)."""
    x = _clean(features)
    if not x:
        return None
    with _LOCK:
        m = _load()
        if m["n"] < _MIN_TRAIN:
            return None
        try:
            proba = m["model"].predict_proba_one(x)
        except Exception:
            return None
    if not proba:
        return None
    p_up = proba.get(True, proba.get(1, 0.5))
    return round(float(min(1.0, max(0.0, p_up))), 4)


def train_from_journal(max_rows: int = 4000) -> dict:
    """Bootstrap the model from closed trades: features from decision_snapshot.market_context
    .filters, label ``up = (direction==LONG) == (net_pnl>0)``. Idempotent-ish (adds samples).
    Returns {learned, scanned}. Never raises."""
    learned = scanned = 0
    try:
        from trading import state
        journal = state.load_json("journal.json", None)
        rows = journal if isinstance(journal, list) else (journal or {}).get("trades", [])
        for r in list(rows)[-max_rows:]:
            scanned += 1
            try:
                d = str(r.get("direction", "")).upper()
                pnl = r.get("net_pnl")
                if d not in ("LONG", "SHORT") or pnl is None or float(pnl) == 0.0:
                    continue
                snap = r.get("decision_snapshot") or {}
                mc = snap.get("market_context") or {} if isinstance(snap, dict) else {}
                feats = _features_from_filters(mc.get("filters") or {})
                # add cheap numeric context features when present (same names live can supply)
                for ck in ("pct_change_24h", "funding_rate_entry", "fear_greed_index"):
                    v = r.get(ck, mc.get(ck) if isinstance(mc, dict) else None)
                    if v is not None:
                        try:
                            feats["c_" + ck] = float(v)
                        except (TypeError, ValueError):
                            pass
                if not feats:
                    continue
                up = (d == "LONG") == (float(pnl) > 0.0)
                learn(feats, up)
                learned += 1
            except Exception:
                continue
    except Exception:
        pass
    _save()
    return {"learned": learned, "scanned": scanned, "n": _load()["n"]}


def ensure_trained() -> None:
    """Lazily bootstrap once from the journal so predict() works from process start."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    with _LOCK:
        if _BOOTSTRAPPED:
            return
        _BOOTSTRAPPED = True
    if _load()["n"] < _MIN_TRAIN:
        train_from_journal()


def status() -> dict:
    m = _load()
    return {"trained_samples": m["n"], "ready": m["n"] >= _MIN_TRAIN, "min_train": _MIN_TRAIN}
