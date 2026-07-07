"""Tests for nodes/micro_transformer_node.py — cloned-LLM node (Phase C)."""
import random

import pytest

from core.node_protocol import NodeProtocol
from nodes.micro_transformer_node import CInferenceKernel, MicroTransformerNode, StreamTokenizer


def _toy(n=160, seed=3):
    rnd = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        a, b = rnd.random(), rnd.random()
        X.append([a, b, rnd.random()])
        y.append(1 if a + b > 1.0 else 0)           # learnable rule
    return X, y


def test_tokenizer_handles_any_data():
    tok = StreamTokenizer(n_bins=8).fit([[0.1, 5.0], [0.9, -2.0], [0.5, 0.0]])
    row_tokens = tok.encode_row([0.4, 1.0])
    assert len(row_tokens) == 2 and all(t >= 2 for t in row_tokens)
    text_tokens = tok.encode_text("btc funding spike")
    assert text_tokens and all(2 <= t < 256 + 2 for t in text_tokens)


def test_satisfies_node_protocol_and_learns():
    X, y = _toy()
    node = MicroTransformerNode(epochs=40)
    assert isinstance(node, NodeProtocol)            # enforced interface
    node.fit(X[:120], y[:120])
    assert node.losses[-1] < node.losses[0], "training loss did not decrease"
    proba = node.predict_proba(X[120:])
    assert len(proba) == 40 and all(0.0 <= p <= 1.0 for p in proba)
    acc = sum(int(p == t) for p, t in zip(node.predict(X[120:]), y[120:])) / 40
    assert acc >= 0.6, f"generative classifier failed to learn (acc={acc})"


def test_c_kernel_generates_with_own_weights(tmp_path):
    kern = CInferenceKernel()
    if not kern.available():
        pytest.skip("llama2.c binary not built")
    model_bin = kern.export_tiny(tmp_path / "tiny.bin", dim=32, n_layers=1, n_heads=2)
    assert model_bin.exists() and model_bin.stat().st_size > 10_000
    out = kern.generate(model_bin, steps=8)
    assert isinstance(out, str)                      # C inference ran end-to-end
