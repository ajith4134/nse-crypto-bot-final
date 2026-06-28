"""trading/brain/sentiment.py — financial news sentiment scoring (T8.7).

Vendor-first: the default scorer is **VADER** (vendored pure-Python lexicon sentiment at
`vendor/vaderSentiment/`), boosted with a finance lexicon (beat/miss/upgrade/probe/…) so
headline tone maps to a [-1,1] compound score on CPU with no model download. **FinBERT**
(ProsusAI, transformers/torch) is wired as a gated optional backend — it activates when
`backend='finbert'`/`'auto'` AND transformers is installed; otherwise it cleanly falls
back to VADER. So the capability ships and is offline-testable; FinBERT is the upgrade.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from vendor.vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Finance-specific lexicon boosts (VADER's general lexicon under-weights these).
_FINANCE_LEXICON = {
    "beat": 2.5, "beats": 2.5, "miss": -2.5, "misses": -2.5, "upgrade": 2.5,
    "downgrade": -2.5, "bullish": 2.8, "bearish": -2.8, "rally": 2.2, "surge": 2.5,
    "soar": 2.6, "plunge": -2.6, "crash": -3.0, "slump": -2.2, "tumble": -2.4,
    "probe": -2.0, "fraud": -3.2, "default": -2.8, "halt": -1.8, "lawsuit": -2.0,
    "guidance": 0.5, "outperform": 2.5, "underperform": -2.5, "buyback": 1.8,
    "dividend": 1.2, "bankruptcy": -3.2, "record": 1.5, "growth": 1.5, "loss": -1.8,
}


@dataclass
class SentimentScorer:
    """Score text tone in [-1,1]. VADER (vendored) default; FinBERT optional/gated."""
    backend: str = "vader"             # vader | finbert | auto
    _vader: SentimentIntensityAnalyzer = field(default=None, init=False)
    _finbert = None
    _active: str = field(default="vader", init=False)

    def __post_init__(self) -> None:
        self._vader = SentimentIntensityAnalyzer()
        self._vader.lexicon.update(_FINANCE_LEXICON)
        if self.backend in ("finbert", "auto"):
            self._try_finbert()

    def _try_finbert(self) -> None:
        try:                            # heavy/optional — only if installed
            from transformers import pipeline
            self._finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert")
            self._active = "finbert"
        except Exception:
            self._finbert = None
            if self.backend == "finbert":
                # explicit finbert requested but unavailable → honest fallback
                self._active = "vader(finbert-unavailable)"
            else:
                self._active = "vader"

    @property
    def active_backend(self) -> str:
        return self._active

    @staticmethod
    def _label(compound: float) -> str:
        return "positive" if compound > 0.05 else ("negative" if compound < -0.05 else "neutral")

    def score(self, text: str) -> dict:
        if not text:
            return {"compound": 0.0, "label": "neutral", "backend": self._active}
        if self._finbert is not None:
            try:
                r = self._finbert(text[:512])[0]
                lab = r["label"].lower()
                sign = 1.0 if lab == "positive" else (-1.0 if lab == "negative" else 0.0)
                comp = round(sign * float(r["score"]), 4)
                return {"compound": comp, "label": self._label(comp), "backend": "finbert"}
            except Exception:
                pass
        comp = round(self._vader.polarity_scores(text)["compound"], 4)
        return {"compound": comp, "label": self._label(comp), "backend": "vader"}

    def score_many(self, texts: list[str]) -> list[dict]:
        return [self.score(t) for t in texts]
