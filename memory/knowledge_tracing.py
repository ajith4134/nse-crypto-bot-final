"""memory/knowledge_tracing.py — EduKTM Deep Knowledge Tracing mastery (Phase P4.4, 2nd model).

The blueprint-named mastery model, added alongside FSRS per the reuse-real-code-first policy
(use the named/most-capable real project even if heavy). Wraps **EduKTM's DKT** (Deep
Knowledge Tracing, an RNN over the learner's (topic, correct) interaction sequence) to
estimate per-topic mastery = P(answer correct next).

Reuse: EduKTM (pip, torch) does the model + training; we only build the one-hot encoding
(idx = topic_id + num_topics*correct) and a per-topic readout from `dkt_model`. Heavier than
FSRS (needs torch + a few epochs) — that's intentional: it's the named project. Seeded for
determinism; CPU-only; offline. Gated: if EduKTM/torch is unavailable it degrades to a
frequency baseline so callers never crash.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KnowledgeTracer:
    topics: list                                     # ordered topic names → ids
    hidden_size: int = 16
    num_layers: int = 1
    seed: int = 0
    sequences: list = field(default_factory=list, init=False)   # [[(topic, correct), ...], ...]
    _model: object = field(default=None, init=False)
    _ok: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.topic2id = {t: i for i, t in enumerate(self.topics)}
        self.num_questions = max(1, len(self.topics))

    def add_sequence(self, interactions: list) -> None:
        """interactions = [(topic, correct_bool), ...] — one learner timeline."""
        seq = [(t, int(bool(c))) for t, c in interactions if t in self.topic2id]
        if seq:
            self.sequences.append(seq)

    # ── one-hot encode a sequence → (1, L, 2*num_questions) ──────────────────────
    def _encode(self, seq):
        import torch
        nq = self.num_questions
        mat = torch.zeros(len(seq), 2 * nq)
        for i, (t, c) in enumerate(seq):
            mat[i, self.topic2id[t] + nq * c] = 1.0
        return mat.unsqueeze(0)                       # batch dim

    def fit(self, *, epoch: int = 10, lr: float = 0.01) -> dict:
        if not self.sequences:
            return {"ok": False, "reason": "no interactions"}
        try:
            import torch
            from EduKTM import DKT
            torch.manual_seed(self.seed)
            loader = [self._encode(s) for s in self.sequences]   # batch_size=1 each (var length)
            self._model = DKT(self.num_questions, self.hidden_size, self.num_layers)
            self._model.train(loader, epoch=epoch, lr=lr)
            self._ok = True
            return {"ok": True, "model": "EduKTM.DKT", "sequences": len(self.sequences),
                    "epochs": epoch}
        except Exception as exc:
            self._ok = False
            return {"ok": False, "reason": f"{type(exc).__name__}: {str(exc)[:80]}"}

    # ── per-topic mastery = P(correct next), from the last interaction step ──────
    def mastery(self) -> dict:
        if not self._ok or self._model is None or not self.sequences:
            return self._baseline()
        try:
            import torch
            net = self._model.dkt_model
            net.eval()
            with torch.no_grad():
                pred = net(self._encode(self.sequences[-1]))      # (1, L, num_questions)
            last = pred[0, -1, :]
            return {t: round(float(last[i]), 4) for t, i in self.topic2id.items()}
        except Exception:
            return self._baseline()

    def _baseline(self) -> dict:
        """Frequency-of-correct per topic (no torch / unfit) so callers still get numbers."""
        agg: dict = {}
        for seq in self.sequences:
            for t, c in seq:
                a = agg.setdefault(t, [0, 0])
                a[0] += c
                a[1] += 1
        return {t: round(agg.get(t, [0, 1])[0] / max(1, agg.get(t, [0, 1])[1]), 4)
                for t in self.topics}

    def status(self) -> dict:
        return {"engine": "EduKTM.DKT", "fitted": self._ok, "topics": len(self.topics),
                "sequences": len(self.sequences), "mastery": self.mastery()}
