"""cognition/affect.py — the brain's affect/mood channel (Phase P4.8).

A cheap, real-time CPU emotion read on text — the "affect channel" of the personality. Three
tiers, each a real reused tool, degrading gracefully so it always works offline:

  1. **GoEmotions** (transformers, 28-label RoBERTa) — the richest read, GATED behind
     ``BRAIN_GOEMOTIONS=1`` (defers the ~120-500 MB model download); reuses the already-installed
     transformers + torch.
  2. **NRCLex** (pure-Python NRC emotion lexicon) — the light real tier: 10 affect dimensions
     (joy/anger/fear/trust/…/positive/negative) with no model, no network at call time.
  3. **keyword stub** — a deterministic positive/negative fallback if even NRCLex is unavailable,
     so tests and offline demos never break.

``Mood`` also keeps a running EMA mood vector (valence + arousal) so the brain has a persistent,
slowly-shifting *mood*, not just per-utterance emotion — updated as it reads/thinks/trades.
"""
from __future__ import annotations

import os

# NRC's 8 emotions + 2 sentiments → a stable ordered affect vocabulary.
_AFFECTS = ("joy", "trust", "anticipation", "surprise", "fear", "anger", "sadness", "disgust",
            "positive", "negative")
# crude valence weights for collapsing an affect dict into a single valence in [-1, 1].
_VALENCE = {"joy": 1, "trust": .6, "anticipation": .3, "surprise": .1, "positive": 1,
            "fear": -.7, "anger": -.8, "sadness": -.8, "disgust": -.7, "negative": -1}
_AROUSAL = {"anger": 1, "fear": 1, "surprise": .8, "joy": .7, "anticipation": .6, "disgust": .5,
            "sadness": .3, "trust": .2, "positive": .4, "negative": .5}

_POS = ("good", "up", "win", "won", "profit", "great", "success", "gain", "beat", "happy")
_NEG = ("bad", "down", "loss", "lose", "risk", "fail", "crash", "drawdown", "fear", "sad")


def _stub_scores(text: str) -> dict:
    t = (text or "").lower()
    pos = sum(w in t for w in _POS)
    neg = sum(w in t for w in _NEG)
    n = pos + neg or 1
    return {"positive": pos / n, "negative": neg / n}


def _nrclex_scores(text: str) -> dict | None:
    try:
        from nrclex import NRCLex
        n = NRCLex()
        n.load_raw_text(text or "")
        freq = dict(n.affect_frequencies)
        return {k: float(freq.get(k, 0.0)) for k in _AFFECTS} if freq else None
    except Exception:
        return None


class _GoEmotions:
    """Lazy, cached GoEmotions pipeline (gated). Maps its 28 labels onto our affect vocab."""

    _PIPE = None
    _MAP = {"joy": "joy", "amusement": "joy", "excitement": "anticipation", "love": "joy",
            "optimism": "anticipation", "gratitude": "trust", "admiration": "trust",
            "approval": "positive", "caring": "trust", "pride": "joy", "relief": "joy",
            "surprise": "surprise", "realization": "surprise", "curiosity": "anticipation",
            "fear": "fear", "nervousness": "fear", "anger": "anger", "annoyance": "anger",
            "disapproval": "negative", "disgust": "disgust", "sadness": "sadness",
            "grief": "sadness", "remorse": "sadness", "disappointment": "sadness",
            "embarrassment": "sadness", "confusion": "surprise", "desire": "anticipation"}

    @classmethod
    def scores(cls, text: str) -> dict | None:
        # active by DEFAULT (model is downloaded); tests/CI set BRAIN_NO_MODELS=1 to force the
        # fast lexicon tier (no model load, deterministic, offline).
        if os.getenv("BRAIN_NO_MODELS") == "1":
            return None
        try:
            if cls._PIPE is None:
                from transformers import pipeline
                cls._PIPE = pipeline("text-classification",
                                     model="SamLowe/roberta-base-go_emotions", top_k=None)
            out = {k: 0.0 for k in _AFFECTS}
            for d in cls._PIPE(text or "")[0]:
                tgt = cls._MAP.get(d["label"])
                if tgt:
                    out[tgt] += float(d["score"])
                    out["positive" if _VALENCE.get(tgt, 0) >= 0 else "negative"] += \
                        float(d["score"]) * 0.3
            s = sum(out.values()) or 1.0
            return {k: v / s for k, v in out.items()}
        except Exception:
            return None


class Mood:
    """Per-utterance emotion + a persistent EMA mood (valence/arousal)."""

    def __init__(self, *, ema: float = 0.3):
        self.ema = float(ema)
        self.valence = 0.0      # running mood valence  [-1, 1]
        self.arousal = 0.0      # running mood arousal   [0, 1]
        self.reads = 0
        self.engine = "stub"

    def read(self, text: str) -> dict:
        """Emotion read of ``text`` (best available tier) + update the running mood."""
        scores = _GoEmotions.scores(text)
        engine = "goemotions"
        if scores is None:
            scores = _nrclex_scores(text)
            engine = "nrclex"
        if scores is None:
            scores = _stub_scores(text)
            engine = "stub"
        self.engine = engine
        val = sum(scores.get(k, 0.0) * w for k, w in _VALENCE.items())
        aro = sum(scores.get(k, 0.0) * w for k, w in _AROUSAL.items())
        # clamp + EMA into the persistent mood
        val = max(-1.0, min(1.0, val))
        aro = max(0.0, min(1.0, aro))
        self.valence = (1 - self.ema) * self.valence + self.ema * val
        self.arousal = (1 - self.ema) * self.arousal + self.ema * aro
        self.reads += 1
        top = sorted(((k, v) for k, v in scores.items()
                      if k not in ("positive", "negative") and v > 0),
                     key=lambda kv: -kv[1])[:3]
        return {"engine": engine, "scores": {k: round(v, 3) for k, v in scores.items() if v > 0},
                "top_emotions": [k for k, _ in top], "valence": round(val, 3),
                "arousal": round(aro, 3), "mood": self.label()}

    def label(self) -> str:
        v, a = self.valence, self.arousal
        if abs(v) < 0.08 and a < 0.15:
            return "neutral"
        if v >= 0:
            return "excited" if a >= 0.4 else "content"
        return "anxious" if a >= 0.4 else "down"

    def status(self) -> dict:
        return {"engine": self.engine, "valence": round(self.valence, 3),
                "arousal": round(self.arousal, 3), "mood": self.label(), "reads": self.reads,
                "tiers": ["goemotions (gated)", "nrclex", "stub"]}
