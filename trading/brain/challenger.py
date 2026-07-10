"""trading/brain/challenger.py — TabPFN-v2 challenger for the TradeOutcomeNet (2026-07-10).

SOTA-replacement scan (ai-scientist ledger #6): TabPFN v2 is a prior-fitted tabular
foundation model (Hollmann et al., Nature 2025 — `pip install tabpfn`, CPU-capable,
zero-cost) that often beats tuned GBDTs on ≤10k-row tables — exactly the TradeOutcomeNet
regime (~3–4k closed trades, ~30 features).

This harness runs an HONEST champion/challenger duel on the SAME protocol the champion
reports on the dashboard: identical features (trade_feature_row), identical folds,
out-of-fold accuracy + log-loss. Result → trading/state/challenger_eval.json. It only
RECOMMENDS: promotion stays behind `TRADE_NET_ENGINE=tabpfn` (read by
TradeOutcomeNet._train_engine), so the live predictor never switches silently.

Heavy (transformer inference per fold) — run from the nice-10 micro-distill daemon or
the CLI (`python -m trading.brain.challenger`), never in the dashboard process.
"""
from __future__ import annotations

import time

_STATE_FILE = "challenger_eval.json"
MAX_ROWS = 1500          # newest closed trades used for the duel (CPU time rail)
FOLDS = 5
PROMOTE_ACC_MARGIN = 0.01     # challenger must beat champion OOF accuracy by ≥1 pt


def _fold_indices(n: int, k: int):
    import numpy as np
    return np.array_split(np.arange(n), k)


def _oof_eval(fit_predict, X, y) -> dict:
    """K-fold OOF accuracy + log-loss for one engine. fit_predict(Xtr, ytr, Xte) → p(win)."""
    import numpy as np
    Xa, ya = np.asarray(X, dtype=float), np.asarray(y, dtype=int)
    n = len(ya)
    probs = np.full(n, np.nan)
    for f in _fold_indices(n, min(FOLDS, n)):
        mask = np.ones(n, dtype=bool)
        mask[f] = False
        if len(set(ya[mask].tolist())) < 2:
            continue
        probs[f] = fit_predict(Xa[mask], ya[mask], Xa[f])
    ok = ~np.isnan(probs)
    if not ok.any():
        return {"oof_accuracy": None, "log_loss": None, "n_scored": 0}
    p = np.clip(probs[ok], 1e-6, 1 - 1e-6)
    yy = ya[ok]
    return {"oof_accuracy": round(float(((p >= 0.5) == (yy == 1)).mean()), 4),
            "log_loss": round(float(-(yy * np.log(p) + (1 - yy) * np.log(1 - p)).mean()), 4),
            "n_scored": int(ok.sum())}


def _champion_fit_predict(Xtr, ytr, Xte, engine_used: list | None = None):
    """The INCUMBENT engine (gated_moe w/ honest fallback) — never the challenger.

    TRADE_NET_ENGINE is masked for this side of the duel: after a tabpfn promotion,
    _train_engine would otherwise train TabPFN for the champion too and the duel would
    score the challenger against itself (2026-07-10 review fix). The engine that
    ACTUALLY trained (gated_moe or the numpy_logreg fallback) is reported via
    `engine_used` so the verdict is never mislabeled."""
    import os as _os
    import numpy as np
    from trading.brain.trade_features import TradeOutcomeNet
    net = TradeOutcomeNet()
    saved = _os.environ.pop("TRADE_NET_ENGINE", None)
    try:
        model = net._train_engine(Xtr.tolist(), ytr.tolist())
    finally:
        if saved is not None:
            _os.environ["TRADE_NET_ENGINE"] = saved
    if engine_used is not None:
        engine_used.append(net.engine)
    if net.engine == "gated_moe":
        return np.asarray(model.predict_proba(Xte.tolist()), dtype=float)
    return np.asarray([model.predict_proba_row(r) for r in Xte], dtype=float)


def _tabpfn_fit_predict(Xtr, ytr, Xte):
    import os as _os
    import numpy as np
    from tabpfn import TabPFNClassifier
    # TabPFN hard-refuses >1000 train rows on CPU unless told we accept the wait; this
    # duel runs nice-10/off-band where minutes are fine (we have no GPU — sole skip rule)
    _os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")
    clf = TabPFNClassifier(device="cpu", n_estimators=2,   # CPU-frugal ensemble
                           ignore_pretraining_limits=True)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)
    win_col = list(clf.classes_).index(1)
    return np.asarray(proba[:, win_col], dtype=float)


def duel(max_rows: int = MAX_ROWS) -> dict:
    """Run the duel on the newest closed trades; persist + return the verdict."""
    from trading import state
    from trading.brain.trade_features import TradeOutcomeNet
    rows = [r for r in (state.load_json("journal.json", []) or [])
            if isinstance(r, dict) and r.get("entry_price")][-max_rows:]
    X, y = TradeOutcomeNet._xy(rows)
    out = {"ts": time.time(), "n_rows": len(X), "folds": FOLDS,
           "protocol": "same features (trade_feature_row) + same K-fold OOF split"}
    if len(X) < 100 or len(set(y)) < 2:
        out["available"] = False
        out["reason"] = "fewer than 100 usable closed trades"
        state.save_json(_STATE_FILE, out)
        return out
    t0 = time.time()
    champ_engines: list = []
    out["champion"] = {**_oof_eval(
        lambda Xtr, ytr, Xte: _champion_fit_predict(Xtr, ytr, Xte, champ_engines), X, y),
        "engine": (champ_engines[-1] if champ_engines else "gated_moe"),
        "seconds": round(time.time() - t0, 1)}
    t0 = time.time()
    try:
        out["challenger"] = {"engine": "tabpfn_v2", **_oof_eval(_tabpfn_fit_predict, X, y),
                             "seconds": round(time.time() - t0, 1)}
    except Exception as e:                    # missing/broken dep → honest report
        out["challenger"] = {"engine": "tabpfn_v2", "error": f"{type(e).__name__}: {e}"[:160]}
    ch, ca = out.get("challenger", {}), out.get("champion", {})
    if ch.get("oof_accuracy") is not None and ca.get("oof_accuracy") is not None:
        beat = (ch["oof_accuracy"] - ca["oof_accuracy"] >= PROMOTE_ACC_MARGIN
                and (ch.get("log_loss") or 9e9) <= (ca.get("log_loss") or 9e9))
        out["verdict"] = ("PROMOTE — set TRADE_NET_ENGINE=tabpfn" if beat else
                          "KEEP champion (challenger did not clear the margin)")
        out["promote"] = beat
    else:
        out["verdict"] = "INCONCLUSIVE (one engine failed to score)"
        out["promote"] = False
    state.save_json(_STATE_FILE, out)
    return out


def status() -> dict:
    from trading import state
    return state.load_json(_STATE_FILE, {"ts": None, "note": "no duel has run yet"})


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(duel(), indent=1, default=str))
