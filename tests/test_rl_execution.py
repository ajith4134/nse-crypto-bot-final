"""AI-scientist idea #8 — RL execution agent (SB3-PPO order slicing beats TWAP)."""
import unittest

from trading.execution.rl_exec_env import ExecutionEnv, twap_episode_reward
from trading.execution.rl_execution import RLExecutionAgent


class TestExecutionEnv(unittest.TestCase):
    def test_env_liquidates_fully(self):
        env = ExecutionEnv(n_steps=8, seed=1)
        env.reset(seed=1)
        done = False
        steps = 0
        while not done and steps < 20:
            _, _, done, _, _ = env.step([0.3])
            steps += 1
        self.assertTrue(done)
        self.assertLessEqual(env.inv, 1e-6)          # final step force-liquidates

    def test_twap_baseline_runs(self):
        env = ExecutionEnv(n_steps=10, seed=2)
        r = twap_episode_reward(env, seed=2)
        self.assertIsInstance(r, float)


class TestRLExecutionAgent(unittest.TestCase):
    def test_plan_without_training(self):
        agent = RLExecutionAgent(n_steps=10)
        plan = agent.plan()
        self.assertEqual(len(plan["schedule"]), 10)
        self.assertAlmostEqual(sum(plan["schedule"]), 1.0, places=2)   # sells the whole inventory
        self.assertFalse(plan["trained"])

    @unittest.skipUnless(RLExecutionAgent().available, "stable-baselines3 not installed")
    def test_trained_agent_beats_or_matches_twap(self):
        agent = RLExecutionAgent(n_steps=10, seed=0).train(total_timesteps=30000)
        self.assertTrue(agent.trained)
        cmp = agent.compare_to_twap(episodes=60)
        # with a learnable timing signal the RL slicer should beat TWAP (small tolerance for variance)
        self.assertGreaterEqual(cmp["edge"], -0.002,
                                f"RL {cmp['rl_mean_reward']} < TWAP {cmp['twap_mean_reward']}")
        plan = agent.plan()
        # a learned slicer may finish early (dump before an adverse move) → 1..n_steps slices,
        # but it must fully liquidate the inventory.
        self.assertTrue(1 <= len(plan["schedule"]) <= 10)
        self.assertAlmostEqual(sum(plan["schedule"]), 1.0, places=2)
        self.assertTrue(plan["trained"])


if __name__ == "__main__":
    unittest.main()
