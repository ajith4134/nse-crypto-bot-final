"""From-scratch NumPy pedagogical core — CANON-11..15 (GRC + NNM videos).

Hand-written numpy ONLY (no torch/sklearn in the math, BY REQUIREMENT): this is
the reference implementation the dashboard's "how a neuron works" view renders.

* ScratchNet — dense layers via np.dot with cached activations (CANON-11),
  seeded small-random weights / zero biases (CANON-12, GRC-08: 0.01*randn),
  ReLU hidden + stable softmax (classification) or linear head (CANON-13),
  categorical cross-entropy / MSE loss, full manual backprop from first
  principles (CANON-14), plain SGD with mini-batches (GRC-19/24 — momentum /
  AdaGrad / RMSProp consciously skipped), per-epoch train+val loss log.
* ScratchRNN — Wxh/Whh/Why + tanh hidden states, full BPTT with ±5 gradient
  clipping, lookback=10 / hidden=64 / lr=0.01 parameter block (CANON-15,
  NNM-15/17/20 — backward pass transcribed from the video).
* validate_forward — load externally trained weights into a ScratchNet and
  verify the forward pass alone reproduces their accuracy (GRC-13 discipline:
  isolate forward-pass correctness from learning-code correctness).
* NodeProtocol wrappers (kind "scratch") so both are neurons in the network.
* run_mnist_check — slow torchvision-MNIST self-check, exposed via __main__
  only (NOT part of the default test suite).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  ScratchNet — dense net from first principles (CANON-11..14)
# --------------------------------------------------------------------------- #
class ScratchNet:
    """layer_sizes e.g. [in, h1, h2, out]; task 'classification'|'regression'."""

    def __init__(self, layer_sizes, task: str = "classification",
                 lr: float = 0.05, seed: int = 0, init_scale: float = 0.01):
        assert len(layer_sizes) >= 2, "need at least input+output layer"
        self.layer_sizes = list(int(s) for s in layer_sizes)
        self.task = task
        self.lr = float(lr)
        rng = np.random.default_rng(seed)                      # CANON-12: seeded
        # init_scale=0.01 is the video-faithful default (GRC-08); low-dim toy
        # problems may need a larger scale (the video's own 4-hour LR/init
        # sweep lesson, GRC-21).
        self.W = [init_scale * rng.standard_normal((a, b))     # small random
                  for a, b in zip(self.layer_sizes[:-1], self.layer_sizes[1:])]
        self.b = [np.zeros((1, b)) for b in self.layer_sizes[1:]]  # zero biases
        self.history: list[dict] = []                          # per-epoch log

    # ---- forward pass with cached activations (CANON-11, GRC-12) ---------- #
    @staticmethod
    def _relu(z):
        return np.maximum(0.0, z)

    @staticmethod
    def _softmax(z):
        z = z - z.max(axis=1, keepdims=True)                   # stable softmax
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def forward(self, X):
        """Returns output; caches every layer's pre/post activation for backprop
        (GRC bookkeeping pattern: keep EVERY intermediate activation)."""
        A = np.asarray(X, float)
        self._acts = [A]                                       # post-activations
        self._zs = []                                          # pre-activations
        n = len(self.W)
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            Z = np.dot(A, W) + b                               # vectorized dense
            self._zs.append(Z)
            if i < n - 1:
                A = self._relu(Z)                              # ReLU hidden
            elif self.task == "classification":
                A = self._softmax(Z)                           # prob head
            else:
                A = Z                                          # linear head
            self._acts.append(A)
        return A

    # ---- losses ------------------------------------------------------------ #
    def loss(self, out, y):
        y = np.asarray(y)
        if self.task == "classification":
            p = np.clip(out[np.arange(len(y)), y.astype(int)], 1e-12, 1.0)
            return float(-np.log(p).mean())                    # categorical CE
        return float(np.mean((out.reshape(-1) - y.reshape(-1)) ** 2))  # MSE

    # ---- backprop from first principles (CANON-14) ------------------------- #
    def backward(self, y):
        """Per-weight partial derivatives, credit assignment layer by layer.
        Uses the simplified softmax+CE combined gradient (dZ = p - onehot)."""
        y = np.asarray(y)
        out = self._acts[-1]
        N = len(y)
        if self.task == "classification":
            dZ = out.copy()
            dZ[np.arange(N), y.astype(int)] -= 1.0
            dZ /= N
        else:
            dZ = 2.0 * (out - y.reshape(out.shape)) / N
        dW = [None] * len(self.W)
        db = [None] * len(self.b)
        for i in range(len(self.W) - 1, -1, -1):
            dW[i] = np.dot(self._acts[i].T, dZ)
            db[i] = dZ.sum(axis=0, keepdims=True)
            if i > 0:
                dA = np.dot(dZ, self.W[i].T)
                dZ = dA * (self._zs[i - 1] > 0)                # ReLU derivative
        return dW, db

    def sgd_step(self, dW, db):
        for i in range(len(self.W)):                           # plain SGD
            self.W[i] -= self.lr * dW[i]
            self.b[i] -= self.lr * db[i]

    # ---- training loop: forward -> loss -> backward -> update (GRC-15) ----- #
    def fit(self, X, y, epochs: int = 10, batch_size: int = 32,
            val: tuple | None = None, shuffle: bool = True, seed: int = 0):
        X = np.asarray(X, float)
        y = np.asarray(y)
        rng = np.random.default_rng(seed)
        for ep in range(int(epochs)):
            idx = rng.permutation(len(X)) if shuffle else np.arange(len(X))
            for s in range(0, len(X), int(batch_size)):        # mini-batches
                bi = idx[s:s + int(batch_size)]
                self.forward(X[bi])
                self.sgd_step(*self.backward(y[bi]))
            row = {"epoch": ep, "train_loss": self.loss(self.forward(X), y)}
            if val is not None:
                Xv, yv = val
                row["val_loss"] = self.loss(self.forward(np.asarray(Xv, float)),
                                            np.asarray(yv))
            self.history.append(row)
        return self

    def predict_proba_rows(self, X):
        return self.forward(np.asarray(X, float))

    def predict(self, X):
        out = self.forward(np.asarray(X, float))
        if self.task == "classification":
            return out.argmax(axis=1)
        return out.reshape(-1)

    def accuracy(self, X, y):
        return float((self.predict(X) == np.asarray(y)).mean())

    # weight export/import used by validate_forward (GRC-13)
    def get_weights(self):
        return [(W.copy(), b.copy()) for W, b in zip(self.W, self.b)]

    def set_weights(self, weights):
        assert len(weights) == len(self.W), "layer count mismatch"
        for i, (W, b) in enumerate(weights):
            W = np.asarray(W, float)
            b = np.asarray(b, float).reshape(1, -1)
            assert W.shape == self.W[i].shape, \
                f"layer {i} W shape {W.shape} != {self.W[i].shape}"
            self.W[i] = W.copy()
            self.b[i] = b.copy()
        return self


def validate_forward(net: ScratchNet, weights, X, y) -> float:
    """GRC-13: load EXTERNALLY trained weights (e.g. a torch state_dict exported
    as [(W, b), ...] with W shaped (fan_in, fan_out)) into the numpy net and
    return forward-pass accuracy — proves the forward pass alone is correct
    before trusting any learning code."""
    net.set_weights(weights)
    return net.accuracy(np.asarray(X, float), np.asarray(y))


# --------------------------------------------------------------------------- #
#  ScratchRNN — hand-written numpy RNN with BPTT (CANON-15, NNM-15/17/19/20)
# --------------------------------------------------------------------------- #
class ScratchRNN:
    """Wxh/Whh/Why + tanh hidden states; full BPTT with ±5 gradient clipping.
    Defaults straight from the video parameter block: lookback=10, hidden=64,
    lr=0.01 (NNM-15). Regression head (scalar y per sequence)."""

    def __init__(self, feature_count: int, hidden_size: int = 64,
                 lookback: int = 10, learning_rate: float = 0.01,
                 seed: int = 42):
        self.feature_count = int(feature_count)
        self.hidden_size = int(hidden_size)
        self.lookback = int(lookback)
        self.learning_rate = float(learning_rate)
        np.random.seed(seed)                                   # NNM-17 verbatim
        self.Wxh = np.random.randn(self.hidden_size, self.feature_count) * 0.01
        self.Whh = np.random.randn(self.hidden_size, self.hidden_size) * 0.01
        self.Why = np.random.randn(1, self.hidden_size) * 0.01
        self.bh = np.zeros((self.hidden_size, 1))
        self.by = np.zeros((1, 1))
        self.history: list[dict] = []

    def forward(self, X):
        """X: (lookback, feature_count). Returns (y, hidden_states) — NNM-19."""
        h = np.zeros((self.hidden_size, 1))
        hidden_states = []
        for t in range(len(X)):
            x_t = np.asarray(X[t], float).reshape(-1, 1)
            h = np.tanh(np.dot(self.Wxh, x_t) + np.dot(self.Whh, h) + self.bh)
            hidden_states.append(h)
        y = np.dot(self.Why, hidden_states[-1]) + self.by
        return float(y[0, 0]), hidden_states

    def backward(self, X, hidden_states, y, y_pred):
        """Full BPTT, transcribed from NNM-20; gradients clipped to ±5."""
        dWxh = np.zeros_like(self.Wxh)
        dWhh = np.zeros_like(self.Whh)
        dWhy = np.zeros_like(self.Why)
        dbh = np.zeros_like(self.bh)
        dby = np.zeros_like(self.by)
        dy = np.array([[y_pred - y]])
        dWhy += np.dot(dy, hidden_states[-1].T)
        dby += dy
        dhnext = np.zeros((self.hidden_size, 1))
        for t in range(len(X) - 1, -1, -1):
            dh = np.dot(self.Why.T, dy) + dhnext               # video-faithful
            dhraw = (1 - hidden_states[t] * hidden_states[t]) * dh  # tanh'
            dbh += dhraw
            dWxh += np.dot(dhraw, np.asarray(X[t], float).reshape(1, -1))
            if t > 0:
                dWhh += np.dot(dhraw, hidden_states[t - 1].T)
            dhnext = np.dot(self.Whh.T, dhraw)
        for dparam in [dWxh, dWhh, dWhy, dbh, dby]:
            np.clip(dparam, -5, 5, out=dparam)                 # grad clip ±5
        self.Wxh -= self.learning_rate * dWxh
        self.Whh -= self.learning_rate * dWhh
        self.Why -= self.learning_rate * dWhy
        self.bh -= self.learning_rate * dbh
        self.by -= self.learning_rate * dby

    def fit(self, sequences, targets, epochs: int = 5):
        """sequences: (N, lookback, F); targets: (N,) scalars."""
        sequences = np.asarray(sequences, float)
        targets = np.asarray(targets, float).reshape(-1)
        for ep in range(int(epochs)):
            total = 0.0
            for X, y in zip(sequences, targets):
                y_pred, hidden_states = self.forward(X)
                total += (y_pred - y) ** 2
                self.backward(X, hidden_states, float(y), y_pred)
            self.history.append({"epoch": ep,
                                 "train_loss": total / max(1, len(sequences))})
        return self

    def predict(self, sequences):
        return np.array([self.forward(X)[0]
                         for X in np.asarray(sequences, float)])


# --------------------------------------------------------------------------- #
#  NodeProtocol wrappers — kind "scratch": the pedagogical core AS neurons
# --------------------------------------------------------------------------- #
class ScratchNetNode(BaseNode):
    """Binary node backed by the from-scratch numpy dense net."""

    kind = "scratch"
    summary = "from-scratch numpy dense NN (CANON-11..14): ReLU+softmax+CE, manual backprop, SGD mini-batches"

    def __init__(self, name: str = "scratch_net", hidden=(32, 16),
                 lr: float = 0.05, epochs: int = 30, seed: int = 0):
        self.name = name
        self.hidden = tuple(int(h) for h in hidden)
        self.lr, self.epochs, self.seed = lr, int(epochs), seed
        self.net: ScratchNet | None = None
        self._mu = self._sd = None

    def fit(self, X: Matrix, y: Labels) -> "ScratchNetNode":
        A = np.asarray(X, float)
        ya = np.asarray(y, int)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._mu = A.mean(axis=0)                              # scaler on TRAIN
        self._sd = A.std(axis=0) + 1e-9
        self.net = ScratchNet([A.shape[1], *self.hidden, 2],
                              task="classification", lr=self.lr, seed=self.seed)
        self.net.fit((A - self._mu) / self._sd, ya, epochs=self.epochs)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = (np.asarray(X, float) - self._mu) / self._sd
        return [float(p) for p in self.net.predict_proba_rows(A)[:, 1]]


class ScratchRNNNode(BaseNode):
    """Binary node backed by the from-scratch numpy RNN (BPTT over a lookback
    window of the row stream; rows must be chronological)."""

    kind = "scratch"
    summary = "from-scratch numpy RNN (CANON-15): Wxh/Whh/Why tanh BPTT, grad clip ±5, lookback 10/hidden 64/lr .01"

    def __init__(self, name: str = "scratch_rnn", lookback: int = 10,
                 hidden_size: int = 64, lr: float = 0.01, epochs: int = 3):
        self.name = name
        self.lookback, self.hidden_size = int(lookback), int(hidden_size)
        self.lr, self.epochs = lr, int(epochs)
        self.rnn: ScratchRNN | None = None
        self._mu = self._sd = None

    def _windows(self, A):
        pad = np.repeat(A[:1], self.lookback - 1, axis=0)      # front-pad so
        B = np.vstack([pad, A])                                # 1 window / row
        return np.stack([B[i:i + self.lookback] for i in range(len(A))])

    def fit(self, X: Matrix, y: Labels) -> "ScratchRNNNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._mu = A.mean(axis=0)
        self._sd = A.std(axis=0) + 1e-9
        seqs = self._windows((A - self._mu) / self._sd)
        tgt = np.asarray(y, float) * 2.0 - 1.0                 # {0,1} -> {-1,+1}
        self.rnn = ScratchRNN(A.shape[1], hidden_size=self.hidden_size,
                              lookback=self.lookback, learning_rate=self.lr)
        self.rnn.fit(seqs, tgt, epochs=self.epochs)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = (np.asarray(X, float) - self._mu) / self._sd
        raw = self.rnn.predict(self._windows(A))               # signed value
        return [float(p) for p in 1.0 / (1.0 + np.exp(-raw))]  # sigmoid squash


# --------------------------------------------------------------------------- #
#  Factories (pool wiring happens in B8, not here)
# --------------------------------------------------------------------------- #
def scratch_net_node(name: str = "scratch_net") -> ScratchNetNode:
    return ScratchNetNode(name)


def scratch_rnn_node(name: str = "scratch_rnn") -> ScratchRNNNode:
    return ScratchRNNNode(name)


# --------------------------------------------------------------------------- #
#  Slow self-check on real MNIST (GRC validation) — __main__ ONLY, not tests
# --------------------------------------------------------------------------- #
def run_mnist_check(max_samples: int = 2000, epochs: int = 3) -> float:
    """Train ScratchNet on a torchvision-MNIST subsample; assert acc > 0.85.
    Downloads MNIST to data/ if absent. Deliberately kept OUT of the default
    test suite (slow, network)."""
    from torchvision import datasets  # local import: torch only for the DATA

    root = "data"
    train = datasets.MNIST(root, train=True, download=True)
    test = datasets.MNIST(root, train=False, download=True)
    Xtr = train.data.numpy()[:max_samples].reshape(-1, 784) / 255.0
    ytr = train.targets.numpy()[:max_samples]
    Xte = test.data.numpy()[:max_samples].reshape(-1, 784) / 255.0
    yte = test.targets.numpy()[:max_samples]
    net = ScratchNet([784, 128, 10], task="classification", lr=0.1, seed=0)
    net.fit(Xtr, ytr, epochs=epochs, batch_size=32, val=(Xte, yte))
    acc = net.accuracy(Xte, yte)
    print(f"ScratchNet MNIST subsample accuracy: {acc:.4f}  "
          f"(history tail: {net.history[-1]})")
    assert acc > 0.85, f"MNIST self-check failed: acc={acc:.4f} <= 0.85"
    return acc


if __name__ == "__main__":
    run_mnist_check()
