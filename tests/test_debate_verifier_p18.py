"""Pillar 18 — adversarial debate + verifier-guided reasoning. Deterministic via injected
chat callables (no network); also exercises the heuristic fallback."""
import unittest


def _yes_chat(msgs, **kw):
    """Fake LLM that always argues yes and scores steps valid."""
    sys = msgs[0]["content"].lower()
    if "step verifier" in sys:
        return "SCORE: 1 — grounded in cited evidence"
    return "Strong case. VOTE: yes"


def _no_chat(msgs, **kw):
    sys = msgs[0]["content"].lower()
    if "step verifier" in sys:
        return "SCORE: 0 — unsupported leap"
    return "Too risky. VOTE: no"


class TestVerifier(unittest.TestCase):
    def test_step_scoring_llm(self):
        from cognition.verifier import StepVerifier
        v = StepVerifier(chat=_yes_chat)
        rep = v.score(["p_up high", "sharpe positive"])
        self.assertEqual(rep["process_reward"], 1.0)
        self.assertTrue(rep["all_valid"])
        self.assertEqual(rep["mode"], "llm")

    def test_step_scoring_reject(self):
        from cognition.verifier import StepVerifier
        v = StepVerifier(chat=_no_chat)
        rep = v.score(["obviously guaranteed profit"])
        self.assertEqual(rep["process_reward"], 0.0)
        self.assertFalse(rep["all_valid"])

    def test_heuristic_fallback_when_no_llm(self):
        import cognition.verifier as vmod
        orig = vmod._default_chat
        vmod._default_chat = lambda: None
        try:
            v = vmod.StepVerifier()      # no chat, no default → heuristic
            good = v.score(["p_up=0.6 because backtest sharpe confirmed the edge"])
            bad = v.score(["obviously this is a guaranteed 100% sure thing to the moon"])
            self.assertEqual(good["mode"], "heuristic")
            self.assertGreater(good["process_reward"], bad["process_reward"])
        finally:
            vmod._default_chat = orig

    def test_best_of_n_ranks_by_reward(self):
        from cognition.verifier import StepVerifier, best_of_n

        def mixed_chat(msgs, **kw):
            # score valid only if the step mentions 'evidence'
            step = msgs[-1]["content"].lower()
            return "SCORE: 1 — ok" if "evidence" in step else "SCORE: 0 — no evidence"
        v = StepVerifier(chat=mixed_chat)
        res = best_of_n([
            {"plan": "weak", "steps": ["gut feel"]},
            {"plan": "strong", "steps": ["evidence: sharpe positive", "evidence: p_up high"]},
        ], v)
        self.assertEqual(res["winner"]["plan"], "strong")
        self.assertEqual(res["n_candidates"], 2)


class TestDebateGate(unittest.TestCase):
    def test_approve_on_yes_and_verified(self):
        from trading.brain.debate_gate import DebateGate
        g = DebateGate(chat=_yes_chat, pass_reward=0.5)
        r = g.assess("BTC/USDT", "LONG",
                     features={"p_up": 0.62, "sharpe": 1.4, "regime": "trend_up"})
        self.assertTrue(r["approved"])
        self.assertGreater(r["size_mult"], 0.0)
        snap = r["decision_snapshot"]
        self.assertEqual(snap["debate_verdict"], "yes")
        self.assertIn("verifier_steps", snap)
        self.assertIn("votes", snap)

    def test_block_on_no(self):
        from trading.brain.debate_gate import DebateGate
        g = DebateGate(chat=_no_chat, pass_reward=0.5)
        r = g.assess("DOGE/USDT", "LONG", features={"p_up": 0.51})
        self.assertFalse(r["approved"])
        self.assertEqual(r["size_mult"], 0.0)


if __name__ == "__main__":
    unittest.main()
