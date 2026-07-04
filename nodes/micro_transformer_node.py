"""nodes/micro_transformer_node.py — the brain's OWN micro-LLM (Phase C, clone-and-extend).

Two real cloned LLM codebases power this (vendor/README.md has commits):

  • nanoGPT (vendor/nanogpt, karpathy @3adf61e) — the exact GPT machinery (token embeddings →
    causal self-attention blocks → lm_head). We instantiate a TINY CPU config and EXTEND it
    with a data-adapter so the same next-token machinery processes ANY data type: numeric
    feature rows are quantile-binned into tokens, text into bytes — this is literally "how an
    LLM processes data", grafted onto the brain as a first-class node.
  • llama2.c (vendor/llama2_c, karpathy @350e04f) — full Llama-2 inference in one C file,
    compiled here (`make run`) as the polyglot hot path. `CInferenceKernel` trains/export a
    tiny Llama with OUR weights (vendor model.py + export.py, repo tokenizer.bin — nothing
    downloaded) and generates through the C binary.

Classification-by-generation: fit() trains next-token prediction on [BOS, row-tokens…, label
token]; predict_proba() reads P(label-1 token | row tokens) from the LLM head — a genuine
generative classifier satisfying the enforced NodeProtocol. CPU-only, seconds to train.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from core.node_protocol import IOSchema, Labels, Matrix, Vector

_VENDOR = Path(__file__).resolve().parent.parent / "vendor"


class StreamTokenizer:
    """Any-data adapter: numeric rows → quantile-bin tokens; text → byte tokens."""

    def __init__(self, n_bins: int = 16):
        self.n_bins = n_bins
        self.edges: list[list[float]] = []           # per-feature quantile edges

    def fit(self, X: Matrix) -> "StreamTokenizer":
        n_feat = len(X[0]) if X else 0
        self.edges = []
        for j in range(n_feat):
            col = sorted(row[j] for row in X)
            self.edges.append([col[min(len(col) - 1, int(len(col) * q / self.n_bins))]
                               for q in range(1, self.n_bins)])
        return self

    def encode_row(self, row: list[float]) -> list[int]:
        toks = []
        for j, v in enumerate(row):
            b = 0
            for e in self.edges[j]:
                if v > e:
                    b += 1
            toks.append(2 + j * self.n_bins + b)     # 0=BOS, 1 reserved
        return toks

    def encode_text(self, text: str) -> list[int]:
        return [2 + (b % 254) for b in text.encode("utf-8")]

    @property
    def vocab_size(self) -> int:
        return 2 + max(1, len(self.edges)) * self.n_bins + 2   # +2 label tokens at the end

    def label_token(self, y: int) -> int:
        return self.vocab_size - 2 + int(y)


class MicroTransformerNode:
    """NodeProtocol node wrapping a tiny nanoGPT trained on the brain's data streams."""

    kind = "micro_llm"

    def __init__(self, name: str = "micro_transformer", n_layer: int = 2, n_head: int = 2,
                 n_embd: int = 32, n_bins: int = 16, epochs: int = 30, lr: float = 3e-3,
                 seed: int = 7):
        self.name = name
        self.tokenizer = StreamTokenizer(n_bins=n_bins)
        self.n_layer, self.n_head, self.n_embd = n_layer, n_head, n_embd
        self.epochs, self.lr, self.seed = epochs, lr, seed
        self.model = None
        self.schema = IOSchema(0, "any feature rows (tokenized)", "P(class 1) via LLM head")
        self.losses: list[float] = []

    # ── the cloned LLM: tiny nanoGPT on CPU ───────────────────────────────────────
    def _build(self, vocab_size: int, block_size: int):
        import torch
        from vendor.nanogpt.model import GPT, GPTConfig
        torch.manual_seed(self.seed)
        cfg = GPTConfig(block_size=block_size, vocab_size=vocab_size,
                        n_layer=self.n_layer, n_head=self.n_head,
                        n_embd=self.n_embd, dropout=0.0, bias=False)
        return GPT(cfg)

    def fit(self, X: Matrix, y: Labels) -> "MicroTransformerNode":
        import torch
        self.tokenizer.fit(X)
        self.schema = IOSchema(len(X[0]), "any feature rows (tokenized)",
                               "P(class 1) via LLM head")
        block = len(X[0]) + 2                          # BOS + row tokens + label
        self.model = self._build(self.tokenizer.vocab_size, block)
        seqs = torch.tensor([[0] + self.tokenizer.encode_row(r) + [self.tokenizer.label_token(t)]
                             for r, t in zip(X, y)], dtype=torch.long)
        inp, tgt = seqs[:, :-1], seqs[:, 1:].clone()
        tgt[:, :-1] = -1                               # loss ONLY on the label position
        opt = torch.optim.AdamW(self.model.parameters(), lr=self.lr)
        self.model.train()
        self.losses = []
        for _ in range(self.epochs):
            _, loss = self.model(inp, tgt)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            self.losses.append(float(loss))
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        import torch
        assert self.model is not None, "fit first"
        self.model.eval()
        seqs = torch.tensor([[0] + self.tokenizer.encode_row(r) for r in X], dtype=torch.long)
        with torch.no_grad():
            logits, _ = self.model(seqs)               # nanoGPT returns last-position logits
        t0, t1 = self.tokenizer.vocab_size - 2, self.tokenizer.vocab_size - 1
        pair = logits[:, -1, [t0, t1]]
        probs = torch.softmax(pair, dim=-1)[:, 1]
        return [float(p) for p in probs]

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


class CInferenceKernel:
    """llama2.c polyglot hot path: train a tiny Llama with OUR weights, run it in C."""

    def __init__(self):
        self.root = _VENDOR / "llama2_c"
        self.binary = self.root / "run"

    def available(self) -> bool:
        return self.binary.exists() and (self.root / "tokenizer.bin").exists()

    def export_tiny(self, out_path: str | Path, dim: int = 64, n_layers: int = 1,
                    n_heads: int = 2, seed: int = 7) -> Path:
        """Create + export a tiny self-owned Llama (no downloads) in llama2.c v0 format."""
        import sys
        import torch
        sys.path.insert(0, str(self.root))          # llama2.c scripts import `model` top-level
        try:
            from vendor.llama2_c.export import legacy_export
            from vendor.llama2_c.model import ModelArgs, Transformer
        finally:
            sys.path.remove(str(self.root))
        torch.manual_seed(seed)
        args = ModelArgs(dim=dim, n_layers=n_layers, n_heads=n_heads,
                         vocab_size=32000, max_seq_len=64, multiple_of=32)
        model = Transformer(args)
        out = Path(out_path)
        legacy_export(model, str(out))
        return out

    def generate(self, model_bin: str | Path, steps: int = 16, temperature: float = 0.8,
                 prompt: str = "") -> str:
        cmd = [str(self.binary), str(model_bin), "-z", str(self.root / "tokenizer.bin"),
               "-n", str(steps), "-t", str(temperature)]
        if prompt:
            cmd += ["-i", prompt]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                             cwd=str(self.root))
        if res.returncode != 0:
            raise RuntimeError(f"llama2.c run failed: {res.stderr[:200]}")
        return res.stdout.strip()
