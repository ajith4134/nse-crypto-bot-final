"""CORTEX B5 — Evolution lane (design §1 T6 signal 5, §6 B5).

Label-free structure/strategy search whose ONLY fitness is CANON-41 mark-to-market
underwater fitness (trading/fitness.py). Because fitness reads realized+unrealized PnL
off a vectorbt equity curve, the KRF hidden-loss bug (optimising a loss that ignores open
drawdown) is structurally impossible here.

Four reused/invented pieces, all fitness-fed by B1:
  * NeatLane        — neat-python 2.0 speciated population; each genome is a feed-forward
                      net mapping a feature row -> a long/flat/short scalar; genomes that
                      fail a cheap zero-cost triage never spend a backtest (CANON-43).
  * zero_cost_triage — synflow/activity-style proxy: reject dead (all-flat / all-on) or
                      anti-correlated signals before the expensive vectorbt evaluation.
  * ReinforceEdgeLearner — GPTSwarm-style policy gradient on per-edge keep-probabilities;
                      reward is the same fitness, baseline-subtracted (variance control).
  * GrowPruneController   — SENN-style plateau trigger for WHEN to grow + GradMax
                      output-preserving neuron init + magnitude prune.

neat-python is optional: absent, NeatLane raises a clear error but the REINFORCE learner,
triage, and grow/prune controller (pure numpy) still work.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

import numpy as np

from trading.fitness import run_signals, underwater_fitness

try:
    import neat
    _HAS_NEAT = True
except Exception:                                                    # pragma: no cover
    neat = None
    _HAS_NEAT = False

__all__ = ["zero_cost_triage", "signals_from_scores", "NeatLane",
           "ReinforceEdgeLearner", "GrowPruneController", "EvolveTelemetry"]


# ═══════════════════════════════════════════════════════════════════════════
# Signal construction + zero-cost triage (spend backtests only on live genomes)
# ═══════════════════════════════════════════════════════════════════════════
def signals_from_scores(scores: np.ndarray, enter: float = 0.3, exit_: float = -0.3
                        ) -> tuple[np.ndarray, np.ndarray]:
    """Map a per-bar score in [-1,1] to boolean (entries, exits).

    Long-only long/flat: enter when score crosses above ``enter``, exit when it
    crosses below ``exit_``. Signals are edge-triggered so vectorbt sees clean fills.
    """
    s = np.asarray(scores, dtype=float).ravel()
    want_long = s > enter
    want_flat = s < exit_
    entries = np.zeros_like(s, dtype=bool)
    exits = np.zeros_like(s, dtype=bool)
    in_pos = False
    for i in range(len(s)):
        if not in_pos and want_long[i]:
            entries[i] = True; in_pos = True
        elif in_pos and want_flat[i]:
            exits[i] = True; in_pos = False
    return entries, exits


def zero_cost_triage(scores: np.ndarray, close: np.ndarray, *,
                     min_activity: float = 0.02, max_activity: float = 0.98) -> tuple[bool, dict]:
    """Cheap proxy deciding whether a genome deserves a full backtest (CANON-43).

    Rejects (returns False) when the signal is degenerate:
      * dead      — almost never long (activity < min_activity),
      * saturated — almost always long (activity > max_activity),
    Otherwise returns a proxy score = corr(score, next-bar return); genuinely
    anti-signal genomes (strongly negative corr) are also rejected. No vectorbt,
    no fees — O(n) numpy only.
    """
    s = np.asarray(scores, dtype=float).ravel()
    c = np.asarray(close, dtype=float).ravel()
    activity = float(np.mean(s > 0.3))
    if activity < min_activity or activity > max_activity:
        return False, {"reason": "degenerate_activity", "activity": activity}
    ret = np.diff(c, prepend=c[0]) / np.maximum(np.abs(c), 1e-9)
    fwd = np.roll(ret, -1)
    if np.std(s) < 1e-9 or np.std(fwd) < 1e-9:
        return False, {"reason": "no_variance", "activity": activity}
    corr = float(np.corrcoef(s, fwd)[0, 1])
    if not np.isfinite(corr):
        corr = 0.0
    return (corr > -0.05), {"proxy_corr": corr, "activity": activity}


@dataclass
class EvolveTelemetry:
    """Every backtest is counted (CANON-43): nothing is evaluated silently."""
    generations: int = 0
    genomes_seen: int = 0
    backtests_run: int = 0
    triaged_out: int = 0
    best_fitness: float = -1e18
    history: list = field(default_factory=list)   # best fitness per generation

    def as_dict(self) -> dict:
        spent = self.backtests_run + self.triaged_out
        return {
            "generations": self.generations, "genomes_seen": self.genomes_seen,
            "backtests_run": self.backtests_run, "triaged_out": self.triaged_out,
            "triage_savings": round(self.triaged_out / spent, 4) if spent else 0.0,
            "best_fitness": round(self.best_fitness, 6),
            "history": [round(h, 6) for h in self.history],
        }


# ═══════════════════════════════════════════════════════════════════════════
# NEAT lane — speciated topology/strategy evolution on mark-to-market fitness
# ═══════════════════════════════════════════════════════════════════════════
_NEAT_CONFIG_TEMPLATE = """\
[NEAT]
fitness_criterion     = max
fitness_threshold     = 1e9
no_fitness_termination = True
pop_size              = {pop_size}
reset_on_extinction   = True

[DefaultGenome]
num_inputs            = {num_inputs}
num_hidden            = {num_hidden}
num_outputs           = 1
initial_connection    = full_direct
feed_forward          = True
compatibility_disjoint_coefficient = 1.0
compatibility_weight_coefficient   = 0.5
conn_add_prob         = 0.5
conn_delete_prob      = 0.2
node_add_prob         = 0.2
node_delete_prob      = 0.1
activation_default    = tanh
activation_options    = tanh relu sigmoid
activation_mutate_rate = 0.1
aggregation_default   = sum
aggregation_options   = sum
aggregation_mutate_rate = 0.0
bias_init_mean        = 0.0
bias_init_stdev       = 1.0
bias_max_value        = 30.0
bias_min_value        = -30.0
bias_mutate_power     = 0.5
bias_mutate_rate      = 0.7
bias_replace_rate     = 0.1
response_init_mean    = 1.0
response_init_stdev   = 0.0
response_max_value    = 30.0
response_min_value    = -30.0
response_mutate_power = 0.0
response_mutate_rate  = 0.0
response_replace_rate = 0.0
weight_init_mean      = 0.0
weight_init_stdev     = 1.0
weight_max_value      = 30.0
weight_min_value      = -30.0
weight_mutate_power   = 0.5
weight_mutate_rate    = 0.8
weight_replace_rate   = 0.1
enabled_default       = True
enabled_mutate_rate   = 0.01

[DefaultSpeciesSet]
compatibility_threshold = 3.0

[DefaultStagnation]
species_fitness_func  = max
max_stagnation        = 15
species_elitism       = 2

[DefaultReproduction]
elitism               = 2
survival_threshold    = 0.2
"""


class NeatLane:
    """neat-python speciated population evolving a long/flat strategy net.

    fitness(genome) = underwater_fitness(run_signals(close, *signals)) with a cheap
    zero-cost triage gate in front so degenerate genomes never spend a backtest.
    """

    def __init__(self, features: np.ndarray, close: np.ndarray, *, pop_size: int = 40,
                 num_hidden: int = 0, fee: float = 0.001, freq: str = "1D", seed: int = 0):
        if not _HAS_NEAT:
            raise RuntimeError("neat-python not installed — NeatLane unavailable")
        Xr = np.asarray(features, dtype=float)
        self.close = np.asarray(close, dtype=float).ravel()
        if Xr.ndim != 2 or Xr.shape[0] != self.close.shape[0]:
            raise ValueError("features must be (T, F) aligned with close (T,)")
        # z-score features so raw-magnitude columns (e.g. price) don't saturate tanh
        # into a constant, degenerate signal (CANON-16 scaling discipline).
        mu, sd = Xr.mean(axis=0), Xr.std(axis=0)
        self.X = (Xr - mu) / np.where(sd > 1e-9, sd, 1.0)
        self.fee, self.freq, self.seed = fee, freq, int(seed)
        self.tel = EvolveTelemetry()
        self._config = self._build_config(pop_size, self.X.shape[1], num_hidden)

    def _build_config(self, pop_size: int, num_inputs: int, num_hidden: int):
        text = _NEAT_CONFIG_TEMPLATE.format(pop_size=pop_size, num_inputs=num_inputs,
                                            num_hidden=num_hidden)
        fd, path = tempfile.mkstemp(suffix=".ini", prefix="neat_cfg_")
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        try:
            return neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                               neat.DefaultSpeciesSet, neat.DefaultStagnation, path)
        finally:
            os.unlink(path)

    def _genome_scores(self, net) -> np.ndarray:
        return np.array([float(net.activate(row)[0]) for row in self.X], dtype=float)

    def genome_fitness(self, genome, config) -> float:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        scores = np.tanh(self._genome_scores(net))          # bound to [-1,1]
        self.tel.genomes_seen += 1
        ok, _ = zero_cost_triage(scores, self.close)
        if not ok:
            self.tel.triaged_out += 1
            return -1.0                                     # rejected without a backtest
        entries, exits = signals_from_scores(scores)
        if not entries.any():
            self.tel.triaged_out += 1
            return -1.0
        self.tel.backtests_run += 1
        pf = run_signals(self.close, entries, exits, fee=self.fee, freq=self.freq)
        fit = float(underwater_fitness(pf))
        return fit if np.isfinite(fit) else -1.0

    def _eval_population(self, genomes, config) -> None:
        for _, genome in genomes:
            genome.fitness = self.genome_fitness(genome, config)

    def evolve(self, n_generations: int = 10):
        """Run NEAT; returns (best_genome, telemetry). Deterministic given seed."""
        import random
        random.seed(self.seed)
        np.random.seed(self.seed)
        pop = neat.Population(self._config)
        best = None
        for _ in range(n_generations):
            pop.run(self._eval_population, 1)
            gen_best = max(pop.population.values(),
                           key=lambda g: (g.fitness if g.fitness is not None else -1e18))
            self.tel.generations += 1
            if gen_best.fitness is not None and gen_best.fitness > self.tel.best_fitness:
                self.tel.best_fitness = float(gen_best.fitness)
                best = gen_best
            self.tel.history.append(self.tel.best_fitness)
        return best, self.tel

    @staticmethod
    def complexity(genome) -> dict:
        """Per-genome complexity (RBT-05): nodes + enabled connections."""
        enabled = sum(1 for c in genome.connections.values() if c.enabled)
        return {"nodes": len(genome.nodes), "connections": enabled}


# ═══════════════════════════════════════════════════════════════════════════
# GPTSwarm-style REINFORCE edge learner
# ═══════════════════════════════════════════════════════════════════════════
class ReinforceEdgeLearner:
    """Learn per-edge keep-probabilities by policy gradient on a fitness reward.

    Each edge has a logit θ_e; a subgraph is sampled (Bernoulli σ(θ_e)); the reward
    (fitness of that subgraph) drives ∇θ_e = (reward − baseline)·(a_e − σ(θ_e)).
    Baseline is an EMA of reward (REINFORCE variance reduction). GPTSwarm applies this
    to agent-communication edges; here the edges are candidate connections in the swarm.
    """

    def __init__(self, n_edges: int, *, lr: float = 0.1, seed: int = 0,
                 baseline_decay: float = 0.9):
        self.n_edges = int(n_edges)
        self.lr = float(lr)
        self.decay = float(baseline_decay)
        self.theta = np.zeros(self.n_edges, dtype=float)
        self._rng = np.random.default_rng(seed)
        self._baseline = 0.0
        self._seen = 0

    def probs(self) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-self.theta))

    def sample(self) -> np.ndarray:
        return (self._rng.random(self.n_edges) < self.probs()).astype(float)

    def update(self, action: np.ndarray, reward: float) -> None:
        a = np.asarray(action, dtype=float).ravel()
        self._seen += 1
        # warm-start baseline to the first reward so early advantage isn't the reward itself
        self._baseline = (reward if self._seen == 1
                          else self.decay * self._baseline + (1 - self.decay) * reward)
        advantage = reward - self._baseline
        self.theta += self.lr * advantage * (a - self.probs())
        np.clip(self.theta, -10.0, 10.0, out=self.theta)

    def optimize(self, fitness_fn, iters: int = 50) -> np.ndarray:
        """Run `iters` sample→reward→update rounds; return the argmax-prob subgraph."""
        for _ in range(iters):
            a = self.sample()
            self.update(a, float(fitness_fn(a)))
        return (self.probs() >= 0.5).astype(float)


# ═══════════════════════════════════════════════════════════════════════════
# Grow/prune — SENN plateau trigger + GradMax init + magnitude prune
# ═══════════════════════════════════════════════════════════════════════════
class GrowPruneController:
    """Decide WHEN to grow (SENN-style plateau), HOW to init (GradMax), and prune."""

    def __init__(self, *, plateau_eps: float = 1e-3, patience: int = 5):
        self.plateau_eps = float(plateau_eps)
        self.patience = int(patience)

    def should_grow(self, loss_history) -> bool:
        """Grow when the recent loss trend has plateaued (improvement < eps).

        SENN uses a natural-gradient magnitude trigger; the observable proxy here is
        a stalled loss curve over `patience` steps — capacity is the likely bottleneck.
        """
        h = np.asarray(list(loss_history), dtype=float)
        if len(h) <= self.patience:
            return False
        window = h[-(self.patience + 1):]
        improvement = window[0] - window[-1]                # positive = still improving
        return improvement < self.plateau_eps

    @staticmethod
    def gradmax_init(fan_in: int, fan_out: int, *, seed: int = 0
                     ) -> tuple[np.ndarray, np.ndarray]:
        """Add a neuron output-preservingly (GradMax): incoming random, OUTGOING zero.

        Zero outgoing weights mean the network's function is unchanged at insertion
        (no output disturbance), while the incoming weights are placed to maximise the
        gradient the new unit will receive — approximated here by a normalized random
        direction.
        """
        rng = np.random.default_rng(seed)
        w_in = rng.standard_normal(fan_in)
        w_in /= (np.linalg.norm(w_in) + 1e-9)
        w_out = np.zeros(fan_out)                           # output-preserving
        return w_in, w_out

    @staticmethod
    def prune(weights: np.ndarray, keep_frac: float = 0.8) -> np.ndarray:
        """Magnitude prune: zero the smallest-|w| entries, keep `keep_frac` of them."""
        w = np.asarray(weights, dtype=float).copy()
        flat = np.abs(w).ravel()
        k = max(1, int(round(keep_frac * flat.size)))
        if k >= flat.size:
            return w
        thresh = np.partition(flat, flat.size - k)[flat.size - k]
        w[np.abs(w) < thresh] = 0.0
        return w
