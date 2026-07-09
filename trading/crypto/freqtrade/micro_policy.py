"""trading/crypto/freqtrade/micro_policy.py — distilled entry micro-policy (invent-beyond #4).

The per-coin decision is EXPENSIVE: PerCoinBrainDecider.tournament() backtests every library
strategy (~153) × brain-weights each — seconds per coin, the exact cycle-time cost that kept
selective entries at ~1/cycle. This module compresses it:

  NIGHTLY (the teacher, off-cycle, nice priority — run_micro_distill):
    for each covered coin, run the FULL tournament once and persist
      • the coin's WINNER strategy + gate verdict (score floor + deflated-Sharpe) — a table
      • per-bar training rows: cheap numpy features(t) → sign(winner_signal(t)) — labels the
        student on what the winner strategy actually said on every bar of the window
    then train ONE LightGBM student over all coins' rows (per-coin winner/gates stay in the
    table — a per-coin 400-row model would just memorize; the table carries the per-coin part).

  LIVE (the student, in-cycle):
    decide(symbol, df) = table lookup (winner + gates) + student inference on the latest bar
    → the same decision dict the executor routes, in ~ms. HONEST ABSTENTION: unknown coin,
    stale table (teacher overdue), or an unconfident student returns None and the caller
    falls back to the full decider — the micro-policy only ever REPLACES compute it can
    faithfully reproduce (teacher agreement is measured and persisted every distill).

Kill-switch: MICRO_POLICY=0. State: micro_policy.json + micro_policy_model.txt (LightGBM
native dump) in trading/state. Paper/live agnostic — it changes decision LATENCY, never the
gates (the persisted verdicts came from the ungated teacher itself).
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import numpy as np

from trading import state

_TABLE_FILE = "micro_policy.json"
_MODEL_FILE = "micro_policy_model.txt"          # LightGBM Booster.save_model text format
_TTL_S = float(os.environ.get("MICRO_POLICY_TTL_S", str(32 * 3600)))   # teacher freshness
_MIN_CONF = float(os.environ.get("MICRO_POLICY_CONF", "0.60"))         # student certainty
_MIN_ROWS = 400                                  # don't train a student on less
_CLASSES = (-1, 0, 1)                            # SHORT / FLAT / LONG (label = class index)

_FEATURE_NAMES = ("r1", "r3", "r6", "r12", "r24", "vol12", "vol48", "mom12", "mom48",
                  "rsi14", "volz48", "range12", "chpos48")


# ── cheap features: pure numpy on the coin's own bars, ~microseconds per row ─────────
def cheap_features(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                   volume: np.ndarray) -> np.ndarray:
    """Feature matrix (n_bars × len(_FEATURE_NAMES)). Rows before the 48-bar warmup hold
    NaN — callers slice them off. No pandas, no TA-lib: this IS the speed budget."""
    c = np.asarray(close, dtype=float)
    n = len(c)
    f = np.full((n, len(_FEATURE_NAMES)), np.nan)
    if n < 50:
        return f
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = np.diff(c, prepend=c[0]) / np.where(c == 0, np.nan, c)
        for j, lag in enumerate((1, 3, 6, 12, 24)):                    # r1..r24
            f[lag:, j] = (c[lag:] - c[:-lag]) / np.where(c[:-lag] == 0, np.nan, c[:-lag])
        for j, w in ((5, 12), (6, 48)):                                # vol12/vol48
            sq = np.convolve(ret * ret, np.ones(w) / w, mode="valid")
            f[w - 1:, j] = np.sqrt(np.maximum(sq, 0))
        for j, w in ((7, 12), (8, 48)):                                # mom12/mom48
            f[w:, j] = c[w:] / np.where(c[:-w] == 0, np.nan, c[:-w]) - 1.0
        up = np.convolve(np.maximum(ret, 0), np.ones(14) / 14, mode="valid")
        dn = np.convolve(np.maximum(-ret, 0), np.ones(14) / 14, mode="valid")
        f[13:, 9] = 100.0 - 100.0 / (1.0 + up / np.where(dn == 0, np.nan, dn))  # rsi14
        v = np.asarray(volume, dtype=float)
        vm = np.convolve(v, np.ones(48) / 48, mode="valid")
        vs = np.array([np.std(v[i - 47:i + 1]) for i in range(47, n)])
        f[47:, 10] = (v[47:] - vm) / np.where(vs == 0, np.nan, vs)     # volz48
        h, lo = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
        rng = np.convolve((h - lo) / np.where(c == 0, np.nan, c), np.ones(12) / 12,
                          mode="valid")
        f[11:, 11] = rng                                               # range12
        for i in range(47, n):                                         # chpos48
            hi, lw = np.max(c[i - 47:i + 1]), np.min(c[i - 47:i + 1])
            f[i, 12] = (c[i] - lw) / (hi - lw) if hi > lw else 0.5
    return f


def _feats_from_df(df) -> np.ndarray:
    return cheap_features(df["close"].to_numpy(dtype=float),
                          df["high"].to_numpy(dtype=float),
                          df["low"].to_numpy(dtype=float),
                          df["volume"].to_numpy(dtype=float))


# ── the student ───────────────────────────────────────────────────────────────────────
class MicroPolicy:
    def __init__(self, booster, table: dict):
        self._booster = booster
        self.table = table                        # {"coins": {sym: {...}}, "trained": {...}}

    # live fast path — returns None to say "fall back to the full decider" (honest abstain)
    def decide(self, symbol: str, df, *, in_position: bool) -> Optional[dict]:
        coin = (self.table.get("coins") or {}).get(symbol)
        if not coin or time.time() - coin.get("ts", 0) > _TTL_S:
            return None                                            # unknown/stale → teacher
        meta = {"source": "micro_policy", "chosen_strategy": coin["winner"],
                "final_score": coin["final"], "sharpe": coin["sharpe"],
                "deflated_psr": coin["deflated_psr"], "deflated_ok": coin["deflated_ok"],
                "teacher_age_s": int(time.time() - coin["ts"]),
                "confidence": coin.get("confidence", 0.0)}
        if not coin["gates_ok"]:                  # tournament verdict: this coin sits out
            meta["action"] = "NEUTRAL"
            meta["reason"] = coin.get("gate_reason", "below threshold")
            if in_position:
                return {"action": "EXIT", "size": 1.0, "tag": coin["winner"], "_brain": meta}
            return {"action": "FLAT", "size": 1.0, "tag": coin["winner"], "_brain": meta}
        if df is None or len(df) < 50:
            return None
        try:
            row = _feats_from_df(df)[-1:]
            if not np.all(np.isfinite(row)):
                return None
            proba = self._booster.predict(row)[0]                  # 3-class softmax
        except Exception:
            return None
        k = int(np.argmax(proba))
        if float(proba[k]) < _MIN_CONF:
            return None                                            # ambiguity → teacher
        meta["p_student"] = round(float(proba[k]), 4)
        last = _CLASSES[k]
        if in_position:
            action = "FLAT" if last > 0 else "EXIT"                # same hold/exit semantics
            meta["action"] = "UP" if action == "FLAT" else "EXIT"
            return {"action": action, "size": 1.0, "tag": coin["winner"], "_brain": meta}
        if last == 0:
            meta["action"] = "NEUTRAL"
            meta["reason"] = "winner flat now (student)"
            return {"action": "FLAT", "size": 1.0, "tag": coin["winner"], "_brain": meta}
        action = "LONG" if last > 0 else "SHORT"
        meta["action"] = "UP" if last > 0 else "DOWN"
        return {"action": action, "size": 1.0, "tag": coin["winner"], "_brain": meta}


# ── singleton loader ────────────────────────────────────────────────────────────────
_MICRO: Any = "unset"


def get_micro() -> Optional[MicroPolicy]:
    """None when MICRO_POLICY=0, lightgbm is missing, or no distill has run yet — callers
    keep using the full decider unchanged."""
    global _MICRO
    if os.environ.get("MICRO_POLICY", "1") not in ("1", "true", "TRUE", "yes"):
        return None
    if _MICRO != "unset":
        return _MICRO
    try:
        table = state.load_json(_TABLE_FILE, {})
        model_path = state.STATE_DIR / _MODEL_FILE
        if not table.get("coins") or not model_path.exists():
            _MICRO = None
            return None
        import lightgbm as lgb
        _MICRO = MicroPolicy(lgb.Booster(model_file=str(model_path)), table)
    except Exception:
        _MICRO = None
    return _MICRO


def invalidate() -> None:
    """Drop the process-wide singleton (a fresh distill just wrote new state)."""
    global _MICRO
    _MICRO = "unset"


# ── the teacher run (nightly, off-cycle) ────────────────────────────────────────────
def distill_once(decider=None, symbols: Optional[list] = None, *,
                 max_symbols: int = int(os.environ.get("MICRO_POLICY_MAX_SYMBOLS", "80")),
                 ) -> dict:
    """Run the FULL per-coin tournament over `symbols`, persist the winner table, train the
    LightGBM student on every bar's winner-signal, and measure teacher agreement. Returns an
    honest report. Heavy BY DESIGN — call from run_micro_distill (nice priority), never from
    a funnel cycle or dashboard thread."""
    t0 = time.monotonic()
    if decider is None:
        from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider
        decider = PerCoinBrainDecider()
    if symbols is None:
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            symbols = CryptoEngineClient().whitelist(segment="futures") or []
        except Exception:
            symbols = []
    symbols = list(symbols)[:max_symbols]
    coins: dict = {}
    X_rows, y_rows = [], []
    errors = 0
    for sym in symbols:
        try:
            t = decider.tournament(sym)
        except Exception:
            errors += 1
            continue
        if t.get("error"):
            errors += 1
            continue
        best = t["best"]
        gates_ok = bool(best["final"] >= decider._min_final and t["deflated_ok"])
        coins[sym] = {"winner": best["name"], "final": best["final"],
                      "sharpe": best["sharpe"], "win_rate": best["win_rate"],
                      "deflated_psr": round(t["deflated_psr"], 4),
                      "deflated_ok": t["deflated_ok"], "gates_ok": gates_ok,
                      "gate_reason": ("" if gates_ok else
                                      "below threshold" if best["final"] < decider._min_final
                                      else "deflated-Sharpe gate"),
                      "confidence": round(min(1.0, max(0.0, best["final"]
                                          / max(decider._min_final, 1e-9) / 4.0)), 3),
                      "ts": time.time()}
        sig, df = t.get("winner_signal"), t.get("df")
        if sig is None or df is None or not gates_ok:
            continue                              # gated-out coins need no student rows
        feats = _feats_from_df(df)
        n = min(len(sig), len(feats))
        F, S = feats[-n:], np.sign(np.asarray(sig[-n:], dtype=float))
        ok = np.all(np.isfinite(F), axis=1) & np.isfinite(S)
        X_rows.append(F[ok])
        y_rows.append(S[ok])
    report = {"symbols": len(symbols), "coins": len(coins), "errors": errors,
              "rows": int(sum(len(x) for x in X_rows))}
    trained = {"ok": False, "reason": f"not enough rows (<{_MIN_ROWS})"}
    if report["rows"] >= _MIN_ROWS:
        try:
            import lightgbm as lgb
            X = np.vstack(X_rows)
            y = np.concatenate(y_rows).astype(int) + 1          # −1/0/+1 → 0/1/2
            ds = lgb.Dataset(X, label=y, feature_name=list(_FEATURE_NAMES))
            booster = lgb.train({"objective": "multiclass", "num_class": 3,
                                 "learning_rate": 0.1, "num_leaves": 31,
                                 "verbosity": -1, "num_threads": 2},
                                ds, num_boost_round=120)
            pred = np.argmax(booster.predict(X), axis=1)
            agree = float(np.mean(pred == y))                   # teacher agreement (fit set)
            booster.save_model(str(state.STATE_DIR / _MODEL_FILE))
            trained = {"ok": True, "rows": len(y), "teacher_agreement": round(agree, 4),
                       "ts": time.time()}
        except Exception as e:
            trained = {"ok": False, "reason": f"{type(e).__name__}: {e}"[:120]}
    table = {"coins": coins, "trained": trained,
             "took_s": round(time.monotonic() - t0, 1), "ts": time.time()}
    state.save_json(_TABLE_FILE, table)
    invalidate()
    return {**report, "trained": trained, "took_s": table["took_s"]}


def status() -> dict:
    """Dashboard view — persisted state only, never loads the model or runs the teacher."""
    d = state.load_json(_TABLE_FILE, {})
    coins = d.get("coins") or {}
    fresh = sum(1 for c in coins.values() if time.time() - c.get("ts", 0) <= _TTL_S)
    return {"enabled": os.environ.get("MICRO_POLICY", "1") in ("1", "true", "TRUE", "yes"),
            "coins": len(coins), "coins_fresh": fresh,
            "gates_ok": sum(1 for c in coins.values() if c.get("gates_ok")),
            "trained": d.get("trained") or {"ok": False, "reason": "no distill yet"},
            "last_distill_took_s": d.get("took_s"), "last_distill_ts": d.get("ts"),
            "ttl_s": _TTL_S, "min_conf": _MIN_CONF}
