"""Feature & target engineering for crypto price series (pure stdlib).

Turns a daily (date, close, volume) series into a supervised dataset: ~12
technical features per row and three aligned targets so different node families
can train on the same data — next-day direction (classification), next-day
return (regression), and a forward-volatility regime label (0/1/2).

No look-ahead: every feature at row i uses only data up to i; targets use i+1.
"""
from __future__ import annotations

START = 20  # need this much history before the first usable row


def _returns(closes: list[float]) -> list[float]:
    return [0.0] + [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def _sma(closes: list[float], i: int, n: int) -> float:
    return sum(closes[i - n + 1: i + 1]) / n


def _std(xs: list[float]) -> float:
    n = len(xs)
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / n) ** 0.5


def _rsi(closes: list[float], i: int, n: int = 14) -> float:
    gains = losses = 0.0
    for k in range(i - n + 1, i + 1):
        ch = closes[k] - closes[k - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100.0 - 100.0 / (1.0 + rs)


FEATURE_NAMES = ["ret1", "ret2", "ret3", "mom5", "mom10",
                 "sma5_r", "sma10_r", "sma20_r", "vol10", "rsi14", "vol_chg"]


def build(rows: list[tuple]) -> dict:
    """rows: ascending (date, close, volume). Returns dict with X and 3 targets."""
    closes = [r[1] for r in rows]
    vols = [r[2] for r in rows]
    rets = _returns(closes)
    abs_r = [abs(r) for r in rets]

    dates, X, y_dir, y_ret = [], [], [], []
    y_vol_high = []                       # causal "big move tomorrow?" target
    fwd_vol = []
    for i in range(START, len(closes) - 1):
        feat = [
            rets[i], rets[i - 1], rets[i - 2],
            closes[i] / closes[i - 5] - 1,
            closes[i] / closes[i - 10] - 1,
            closes[i] / _sma(closes, i, 5) - 1,
            closes[i] / _sma(closes, i, 10) - 1,
            closes[i] / _sma(closes, i, 20) - 1,
            _std(rets[i - 9: i + 1]),
            _rsi(closes, i) / 100.0,
            (vols[i] / vols[i - 1] - 1) if vols[i - 1] else 0.0,
        ]
        nxt = closes[i + 1] / closes[i] - 1
        dates.append(rows[i][0])
        X.append(feat)
        y_dir.append(1 if nxt > 0 else 0)
        y_ret.append(nxt)
        fwd_vol.append(_std(rets[i - 4: i + 1]))
        # volatility target: will |next return| exceed the recent (trailing-20)
        # median move? Threshold uses only data up to i (causal) -> no leakage.
        win = abs_r[max(0, i - 19): i + 1]
        med = sorted(win)[len(win) // 2]
        y_vol_high.append(1 if abs(rets[i + 1]) > med else 0)

    # Volatility-regime label: terciles of forward vol (0=calm,1=normal,2=chaotic)
    order = sorted(range(len(fwd_vol)), key=lambda k: fwd_vol[k])
    y_regime = [0] * len(fwd_vol)
    third = max(1, len(order) // 3)
    for rank, idx in enumerate(order):
        y_regime[idx] = 0 if rank < third else (2 if rank >= 2 * third else 1)

    return {"dates": dates, "feature_names": FEATURE_NAMES, "X": X,
            "y_direction": y_dir, "y_return": y_ret, "y_regime": y_regime,
            "y_vol_high": y_vol_high}
