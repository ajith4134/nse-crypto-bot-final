"""DeepLOB price-direction prediction from recorded depth snapshots (CPU).

Model: vendor/lob_deep_learning (Jeonghwan-Cheon @91b8d2e) models/deeplob.py — the PyTorch
DeepLOB (Zhang/Zohren/Roberts 2019) with lighten=True, whose conv stack reduces exactly a
5-level book (20 columns: ask_p/ask_q/bid_p/bid_q × 5) — matching NSE depth and our capped
crypto rings. Labels follow the FI-2010 convention: smoothed future-mid direction vs a
threshold. Training data accumulates automatically in trading/data/depth/*.jsonl (written by
trading/brain/psychology.py on every evaluate()).

Honest by design: predict() returns None until a trained model exists; train() reports how
much data it had. No pretrained weights are shipped anywhere public for live 5-level books —
the recorder + this trainer IS the path to the capability.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DEPTH_DIR = Path(__file__).resolve().parents[1] / "data" / "depth"
MODEL_PATH = DEPTH_DIR / "deeplob_5lvl.pt"
LEVELS = 5
WINDOW = 100          # snapshots per sample (DeepLOB input length)
HORIZON = 10          # predict smoothed mid direction this many snapshots ahead
ALPHA = 0.0002        # FI-2010-style flat threshold on relative mid change
MIN_TRAIN_SAMPLES = 500


def _snapshot_vec(row: dict) -> list[float] | None:
    """One recorded snapshot → FI-2010 column order [ask_p,ask_q,bid_p,bid_q] × level."""
    bids, asks = row.get("bids") or [], row.get("asks") or []
    if len(bids) < LEVELS or len(asks) < LEVELS:
        return None
    vec: list[float] = []
    for i in range(LEVELS):
        vec += [asks[i][0], asks[i][1], bids[i][0], bids[i][1]]
    return vec


def load_series(path: Path) -> np.ndarray:
    rows = []
    try:
        for line in path.read_text().splitlines():
            try:
                v = _snapshot_vec(json.loads(line))
            except json.JSONDecodeError:
                continue
            if v:
                rows.append(v)
    except OSError:
        pass
    return np.asarray(rows, dtype=np.float32)


def make_samples(series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows + FI-2010 smoothed labels (0=down, 1=flat, 2=up)."""
    if len(series) < WINDOW + HORIZON + 1:
        return np.empty((0,)), np.empty((0,))
    mid = (series[:, 0] + series[:, 2]) / 2.0          # (ask_p1 + bid_p1) / 2
    # z-score per file (train-time normalisation; predict applies its own ring z-score)
    mu, sd = series.mean(axis=0), series.std(axis=0)
    sd[sd == 0] = 1.0
    norm = (series - mu) / sd
    X, y = [], []
    for t in range(WINDOW, len(series) - HORIZON):
        m_future = mid[t + 1: t + 1 + HORIZON].mean()
        rel = (m_future - mid[t]) / mid[t] if mid[t] else 0.0
        label = 2 if rel > ALPHA else (0 if rel < -ALPHA else 1)
        X.append(norm[t - WINDOW: t])
        y.append(label)
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int64)


def _model():
    import torch
    from vendor.lob_deep_learning.models.deeplob import Deeplob
    m = Deeplob(lighten=True)
    m.device = torch.device("cpu")
    return m


def train(epochs: int = 5, lr: float = 1e-3, batch: int = 64) -> dict:
    """Train on ALL recorded depth files; save weights when there is enough data."""
    import torch
    files = sorted(DEPTH_DIR.glob("*.jsonl"))
    Xs, ys = [], []
    for f in files:
        X, y = make_samples(load_series(f))
        if len(X):
            Xs.append(X)
            ys.append(y)
    if not Xs:
        return {"trained": False, "reason": "no depth recordings yet", "files": len(files)}
    X = np.concatenate(Xs)
    y = np.concatenate(ys)
    if len(X) < MIN_TRAIN_SAMPLES:
        return {"trained": False, "reason": f"only {len(X)} samples (<{MIN_TRAIN_SAMPLES}); "
                                            "keep the loops running to record more depth",
                "files": len(files), "samples": int(len(X))}
    model = _model()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = torch.nn.CrossEntropyLoss()
    Xt = torch.from_numpy(X).unsqueeze(1)              # (N, 1, WINDOW, 20)
    yt = torch.from_numpy(y)
    n = len(Xt)
    model.train()
    for ep in range(epochs):
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            opt.zero_grad()
            out = model(Xt[idx])
            loss = lossf(out, yt[idx])
            loss.backward()
            opt.step()
            tot += float(loss) * len(idx)
        logger.info("deeplob epoch %d loss %.4f", ep + 1, tot / n)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    return {"trained": True, "samples": int(n), "files": len(files),
            "final_loss": round(tot / n, 5), "model": str(MODEL_PATH)}


_CACHED = None


def predict_prob_up(ring) -> float | None:
    """P(up) for the latest window of a live snapshot ring; None until a model is trained."""
    global _CACHED
    if not MODEL_PATH.exists():
        return None
    snaps = list(ring)[-WINDOW:]
    if len(snaps) < WINDOW:
        return None
    rows = []
    for s in snaps:
        if len(s.bids) < LEVELS or len(s.asks) < LEVELS:
            return None
        rows.append([x for i in range(LEVELS)
                     for x in (s.asks[i][0], s.asks[i][1], s.bids[i][0], s.bids[i][1])])
    try:
        import torch
        if _CACHED is None:
            m = _model()
            m.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
            m.eval()
            _CACHED = m
        arr = np.asarray(rows, dtype=np.float32)
        mu, sd = arr.mean(axis=0), arr.std(axis=0)
        sd[sd == 0] = 1.0
        x = torch.from_numpy((arr - mu) / sd).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            p = _CACHED(x)[0]                          # [down, flat, up]
        return float(p[2])
    except Exception:
        logger.debug("deeplob predict failed", exc_info=True)
        return None
