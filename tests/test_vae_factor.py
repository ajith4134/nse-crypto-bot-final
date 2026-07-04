"""AI-scientist idea #9 — VAE factor node + synthetic scenario generator."""
import unittest

import numpy as np

from core.node_protocol import NodeProtocol
from nodes.vae_factor import VAEFactorNode, vae_factor_node


def _dataset(n=400, d=8, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    # label depends on a couple of features + a nonlinear interaction (VAE latents should capture it)
    logit = 1.4 * X[:, 0] - 1.1 * X[:, 2] + 0.8 * X[:, 1] * X[:, 3]
    y = (logit + rng.normal(scale=0.5, size=n) > 0).astype(int)
    return X.tolist(), y.tolist()


class TestVAEFactor(unittest.TestCase):
    def test_protocol_and_fit_predict(self):
        X, y = _dataset()
        node = vae_factor_node("vae_test")
        self.assertIsInstance(node, NodeProtocol)
        node.epochs = 40                                    # keep the test quick
        node.fit(X, y)
        p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        acc = np.mean([int(pi >= 0.5) == yi for pi, yi in zip(p, y)])
        self.assertGreater(acc, 0.6, f"VAE factor node no better than chance (acc={acc:.3f})")

    def test_scenario_generator(self):
        X, y = _dataset(seed=1)
        node = VAEFactorNode(name="vae_gen", latent=5, epochs=40)
        node.fit(X, y)
        gen = node.generator()
        syn = gen.generate(n=32)
        # torch present in this env → generator should produce rows in the original feature space
        self.assertEqual(len(syn), 32)
        self.assertEqual(len(syn[0]), len(X[0]))
        # stress scenarios (scale>1) should be more dispersed than the base sample
        base = np.asarray(gen.generate(n=200, scale=1.0))
        stress = np.asarray(gen.generate(n=200, scale=2.5))
        self.assertGreater(stress.std(), base.std())

    def test_latents_are_decorrelated(self):
        # the β-VAE KL pressure should keep latent factors less correlated than the raw features.
        X, y = _dataset(seed=2)
        node = VAEFactorNode(name="vae_dc", latent=6, beta=2.0, epochs=60)
        node.fit(X, y)
        if node.fell_back:
            self.skipTest("torch unavailable — logistic fallback has no latents")
        Z = node._latents((np.asarray(X, np.float32) - node._mu_mean) / node._mu_std)
        # mean absolute off-diagonal correlation of the latents
        C = np.corrcoef(Z, rowvar=False)
        off = C[~np.eye(C.shape[0], dtype=bool)]
        self.assertLess(np.mean(np.abs(off)), 0.6)


if __name__ == "__main__":
    unittest.main()
