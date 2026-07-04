"""CORTEX B8 — live-unseen validation protocol (CANON-42).

Truly-unseen validation: every live directional prediction is APPENDED to a
JSONL ledger the moment it is made (before the outcome exists — no way to
cherry-pick), then scored ONLY after its horizon has matured against the
realized close. A rolling accuracy-over-time series is persisted for the
dashboard (LSTM-16/KRF-17/KRF-20: held-out-only prediction, live-data tests,
rolling accuracy tracking).

Storage (env-overridable, defaults under trading/state/):
  MLNB_VALIDATION_PATH  — the predictions JSONL
  (accuracy series lives next to it as <stem>_accuracy.json)

Realized prices come from ``price_lookup(symbol, matured_ts) -> float`` when
provided; otherwise the cheap local candle store (Freqtrade's downloaded
feather/json candles via data.downloads.locate_freqtrade_1m) is tried, and a
prediction whose price cannot be resolved simply stays pending — never scored
against a guess.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_ROLLING_N = 50


def _jsonl_path() -> Path:
    env = os.environ.get("MLNB_VALIDATION_PATH")
    if env:
        p = Path(env)
    else:
        from trading import state
        p = Path(state.STATE_DIR) / "validation_holdout.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _accuracy_path() -> Path:
    p = _jsonl_path()
    return p.with_name(p.stem + "_accuracy.json")


def record_prediction(ts: float, symbol: str, pred: int | float, horizon: float,
                      *, price_at_pred: float | None = None, meta: dict | None = None) -> dict:
    """Append one live prediction (append-only; scored later by score_matured).

    ts            : unix seconds the prediction was made.
    pred          : direction (+1 up / -1 down; any sign-carrying number).
    horizon       : seconds until the prediction matures.
    price_at_pred : reference price (needed to judge direction at maturity).
    """
    rec = {"ts": float(ts), "symbol": str(symbol), "pred": float(pred),
           "horizon": float(horizon), "price_at_pred": price_at_pred,
           "scored": False}
    if meta:
        rec["meta"] = meta
    with open(_jsonl_path(), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _load_all() -> list[dict]:
    p = _jsonl_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                                    # skip torn line, keep ledger
    return out


def _rewrite(records: list[dict]) -> None:
    p = _jsonl_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in records))
    os.replace(tmp, p)


def _candle_close(symbol: str, ts: float) -> float | None:
    """Best-effort realized close at `ts` from the local Freqtrade candle store."""
    try:
        import pandas as pd
        from data.downloads import locate_freqtrade_1m
        key = str(symbol).split("/")[0].split(":")[0].upper()
        for path in locate_freqtrade_1m():
            if key not in os.path.basename(path).upper():
                continue
            df = pd.read_feather(path) if path.endswith(".feather") else pd.read_json(path)
            tcol = "date" if "date" in df.columns else df.columns[0]
            t = pd.to_datetime(df[tcol], utc=True).astype("int64") / 1e9
            idx = (t - ts).abs().idxmin()
            if abs(float(t.loc[idx]) - ts) > 3600:      # >1h away: not a real match
                return None
            ccol = "close" if "close" in df.columns else df.columns[4]
            return float(df[ccol].loc[idx])
    except Exception:
        return None
    return None


def score_matured(now: float | None = None, *, price_lookup=None) -> dict:
    """Score every matured, still-unscored prediction; persist the rolling
    accuracy series. Predictions whose realized price cannot be resolved stay
    pending (honest: never scored against a guess)."""
    now = float(now if now is not None else time.time())
    records = _load_all()
    lookup = price_lookup or _candle_close
    newly = 0
    for r in records:
        if r.get("scored") or r.get("price_at_pred") is None:
            continue
        matured_at = float(r["ts"]) + float(r["horizon"])
        if matured_at > now:
            continue
        realized = lookup(r["symbol"], matured_at)
        if realized is None:
            continue                                    # stays pending
        realized = float(realized)
        moved_up = realized > float(r["price_at_pred"])
        pred_up = float(r["pred"]) > 0
        r["scored"] = True
        r["realized_price"] = realized
        r["scored_at"] = now
        r["correct"] = bool(moved_up == pred_up)
        newly += 1
    if newly:
        _rewrite(records)

    scored = [r for r in records if r.get("scored")]
    pending = [r for r in records if not r.get("scored")]
    n = len(scored)
    acc = (sum(1 for r in scored if r["correct"]) / n) if n else None
    tail = scored[-_ROLLING_N:]
    roll = (sum(1 for r in tail if r["correct"]) / len(tail)) if tail else None
    summary = {"ts": now, "n_scored": n, "n_pending": len(pending),
               "newly_scored": newly, "accuracy": acc,
               f"rolling_{_ROLLING_N}": roll}

    # rolling accuracy-over-time series for the dashboard (append this point)
    ap = _accuracy_path()
    series = []
    if ap.exists():
        try:
            series = json.loads(ap.read_text())
        except json.JSONDecodeError:
            series = []
    if n:                                               # only meaningful points
        series.append({"ts": now, "n_scored": n, "accuracy": acc,
                       f"rolling_{_ROLLING_N}": roll})
        series = series[-2000:]
        ap.write_text(json.dumps(series))
    summary["series_points"] = len(series)
    return summary
