"""trading/journal/confidence.py — per-symbol Bayesian confidence (T5 §T5.1/§T5.2).

A per-symbol confidence book wired to the ML Network Brain's recalibration loop.
Each symbol tracks a Bayesian win-rate as a Beta(alpha, beta) posterior (uniform
Beta(1,1) prior) and, when the Brain supplied an entry probability, a running
Brier score so we can tell calibration apart from raw hit-rate.

Design notes:
  * No brain import. The Brain is notified purely through the optional
    ``on_recalibrate(symbol, SymbolConfidence)`` hook injected into
    :class:`ConfidenceBook` — keeping this module dependency-free and offline.
  * Everything is robust to missing symbol / missing ``brain_confidence_entry``.
  * Pure, deterministic, JSON-serialisable output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


def _as_prob(value) -> float | None:
    """Coerce a brain confidence to a 0–1 probability.

    Accepts values already in (0, 1]; if it looks like a 0–100 percentage
    (> 1.0), divides by 100. Returns None for missing/invalid, and clamps to
    (0, 1] for safety.

    ``<= 0`` is treated as MISSING, not as a forecast: the brain never enters a
    trade at 0% confidence, so a stored 0.0 is a default-value artifact (and a
    negative is a sentinel). Scoring 0.0 against losses produced fake-perfect
    Brier scores (ETH/USDT brier 0.0 with a 12% win rate, 2026-07-10 audit).
    """
    if value is None:
        return None
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if p > 1.0:
        p = p / 100.0
    if p <= 0.0:
        return None
    if p > 1.0:
        return 1.0
    return p


@dataclass
class SymbolConfidence:
    """Bayesian win-rate + calibration for a single symbol."""

    symbol: str = ""
    alpha: float = 1.0          # Beta prior successes (+1 uniform)
    beta: float = 1.0           # Beta prior failures (+1 uniform)
    wins: int = 0
    losses: int = 0
    brier_sum: float = 0.0      # sum of (predicted - outcome)^2
    brier_count: int = 0

    def update(self, won: bool, predicted_prob: float | None = None) -> None:
        """Record one outcome, optionally accumulating a Brier-score term."""
        if won:
            self.alpha += 1.0
            self.wins += 1
        else:
            self.beta += 1.0
            self.losses += 1
        p = _as_prob(predicted_prob)
        if p is not None:
            outcome = 1.0 if won else 0.0
            self.brier_sum += (p - outcome) ** 2
            self.brier_count += 1

    # ── derived metrics ──────────────────────────────────────────────────────
    @property
    def n(self) -> int:
        """Number of recorded trades (observed wins + losses)."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        """Posterior mean of the Beta win-rate = alpha / (alpha + beta)."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def confidence(self) -> float:
        """Calibrated confidence score in [0, 1].

        We shrink the Beta posterior mean toward the neutral prior 0.5 by a
        sample-size factor ``n / (n + k)`` (k=5 pseudo-trades), so a single
        win/loss can't push confidence to an extreme:

            confidence = 0.5 + (win_rate - 0.5) * n / (n + k)

        With n=0 this is exactly 0.5 (no opinion); as n grows it converges to
        the raw Beta win-rate. k=5 means it takes ~5 trades to earn half the
        distance from neutral.
        """
        k = 5.0
        n = self.n
        shrink = n / (n + k) if n else 0.0
        return 0.5 + (self.win_rate - 0.5) * shrink

    @property
    def brier(self) -> float | None:
        """Mean Brier score over trades that carried a brain prediction, else None.

        Lower is better (0 = perfect, 0.25 = chance for a 0.5 forecast).
        """
        if self.brier_count == 0:
            return None
        return self.brier_sum / self.brier_count

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "n": self.n,
            "wins": self.wins,
            "losses": self.losses,
            "alpha": self.alpha,
            "beta": self.beta,
            "win_rate": self.win_rate,
            "confidence": self.confidence,
            "brier": self.brier,
            "brier_count": self.brier_count,
        }


class ConfidenceBook:
    """Holds per-symbol :class:`SymbolConfidence` and a recalibration hook.

    ``on_recalibrate`` is an optional callable ``(symbol, SymbolConfidence) ->
    None`` invoked after each trade update — this is how the ML Network Brain
    gets notified without this module importing it.
    """

    # book-level (prob, outcome) pairs kept for ECE / reliability bins — aggregates alone
    # can't measure calibration shape. Rebuilt naturally on load (journal replays trades).
    CALIB_CAP = 1000

    def __init__(self, on_recalibrate: Callable[[str, "SymbolConfidence"], None] | None = None):
        self._symbols: dict[str, SymbolConfidence] = {}
        self._calib: list[tuple[float, float]] = []     # (predicted p, outcome 0/1), capped
        self.on_recalibrate = on_recalibrate

    # ── updates ──────────────────────────────────────────────────────────────
    def update_from_trade(self, trade) -> None:
        """Update the symbol's confidence from a closed trade.

        outcome = net_pnl > 0; predicted = brain_confidence_entry (0–1, or 0–100
        auto-scaled). Sets ``trade.brain_correct`` when the brain made a
        directional call (UP/DOWN) and direction is known, else leaves it None.
        Robust to missing symbol / missing brain_confidence_entry.
        """
        symbol = getattr(trade, "symbol", "") or ""
        if symbol not in self._symbols:
            self._symbols[symbol] = SymbolConfidence(symbol=symbol)
        sc = self._symbols[symbol]

        won = (getattr(trade, "net_pnl", 0.0) or 0.0) > 0
        predicted = _as_prob(getattr(trade, "brain_confidence_entry", None))
        sc.update(won, predicted)
        if predicted is not None:
            self._calib.append((predicted, 1.0 if won else 0.0))
            if len(self._calib) > self.CALIB_CAP:
                del self._calib[: len(self._calib) - self.CALIB_CAP]

        # brain_correct: only when a directional prediction was made.
        pred = (getattr(trade, "brain_prediction", "") or "").upper()
        direction = (getattr(trade, "direction", "") or "").upper()
        if pred in ("UP", "DOWN") and direction in ("LONG", "SHORT"):
            # The brain predicting UP aligns with profit on a LONG (and loss on a
            # SHORT); DOWN aligns with profit on a SHORT.
            predicted_up = pred == "UP"
            actual_up = won if direction == "LONG" else (not won)
            trade.brain_correct = (predicted_up == actual_up)
        # else: leave brain_correct as-is (default None)

        if self.on_recalibrate is not None:
            self.on_recalibrate(symbol, sc)

    # ── reads ────────────────────────────────────────────────────────────────
    def get(self, symbol: str) -> SymbolConfidence | None:
        return self._symbols.get(symbol)

    def score(self, symbol: str) -> float | None:
        sc = self._symbols.get(symbol)
        return sc.confidence if sc is not None else None

    def reliability(self, n_bins: int = 10) -> list[dict]:
        """Reliability-diagram bins over the recorded (p, outcome) pairs.

        Each bin: how often the brain SAID p ∈ [lo, hi) vs how often it actually
        won there. A calibrated brain has avg_p ≈ win_rate in every bin."""
        bins = [{"lo": i / n_bins, "hi": (i + 1) / n_bins, "n": 0,
                 "p_sum": 0.0, "won_sum": 0.0} for i in range(n_bins)]
        for p, won in self._calib:
            b = bins[min(int(p * n_bins), n_bins - 1)]
            b["n"] += 1
            b["p_sum"] += p
            b["won_sum"] += won
        return [{"lo": round(b["lo"], 2), "hi": round(b["hi"], 2), "n": b["n"],
                 "avg_p": round(b["p_sum"] / b["n"], 4) if b["n"] else None,
                 "win_rate": round(b["won_sum"] / b["n"], 4) if b["n"] else None}
                for b in bins]

    def ece(self, n_bins: int = 10) -> float | None:
        """Expected Calibration Error = Σ (n_bin/N) · |avg_p − win_rate|; None until
        any forecast-carrying trades exist. 0 = perfectly calibrated."""
        total = len(self._calib)
        if total == 0:
            return None
        err = 0.0
        for b in self.reliability(n_bins):
            if b["n"]:
                err += (b["n"] / total) * abs(b["avg_p"] - b["win_rate"])
        return round(err, 4)

    def as_dict(self) -> dict:
        per_symbol = {s: sc.as_dict() for s, sc in self._symbols.items()}
        brier_sum = sum(sc.brier_sum for sc in self._symbols.values())
        brier_count = sum(sc.brier_count for sc in self._symbols.values())
        total_n = sum(sc.n for sc in self._symbols.values())
        total_wins = sum(sc.wins for sc in self._symbols.values())
        return {
            "symbols": per_symbol,
            "n_symbols": len(self._symbols),
            "total_trades": total_n,
            "overall_win_rate": (total_wins / total_n) if total_n else None,
            "overall_brier": (brier_sum / brier_count) if brier_count else None,
            "ece": self.ece(),
            "reliability": self.reliability(),
            "calib_n": len(self._calib),
        }
