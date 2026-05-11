"""
Reinforcement Learning agent for seed optimization.
Uses Q-learning to learn which seed ranges produce the best coverage improvement.
"""

import random
import math
import logging
import numpy as np
from typing import Optional
from ..core.config import MLConfig

logger = logging.getLogger(__name__)


class RLSeedAgent:
    """
    RL agent that learns to select optimal simulation seeds.

    State: Discretized coverage vector (overall coverage bucket + gap pattern)
    Action: Seed range selection (divided into discrete buckets)
    Reward: Coverage improvement (delta coverage)
    """

    N_COVERAGE_BUCKETS = 20  # 0-5%, 5-10%, ..., 95-100%
    N_SEED_BUCKETS = 50      # Divide seed range into 50 action buckets

    def __init__(self, config: MLConfig):
        self.config = config
        self.seed_min = config.seed_range_min
        self.seed_max = config.seed_range_max
        self.epsilon = config.rl_epsilon
        self.lr = config.rl_learning_rate
        self.gamma = config.rl_discount_factor

        # Q-table: state (coverage bucket) x action (seed bucket)
        self.q_table = np.zeros((self.N_COVERAGE_BUCKETS, self.N_SEED_BUCKETS))

        # Experience replay buffer
        self._history = []
        self._current_state = 0
        self._last_action = 0
        self._llm_bias = None

    def _coverage_to_state(self, coverage_pct: float) -> int:
        """Map coverage percentage to discrete state."""
        bucket = int(coverage_pct / (100.0 / self.N_COVERAGE_BUCKETS))
        return min(bucket, self.N_COVERAGE_BUCKETS - 1)

    def _action_to_seed(self, action: int) -> int:
        """Map action index to a seed value within that bucket."""
        bucket_size = (self.seed_max - self.seed_min) / self.N_SEED_BUCKETS
        bucket_start = int(self.seed_min + action * bucket_size)
        bucket_end = int(bucket_start + bucket_size)
        return random.randint(bucket_start, bucket_end - 1)

    def suggest_seed(self) -> int:
        """Select a seed using epsilon-greedy policy."""
        if random.random() < self.epsilon:
            # Exploration: random action
            action = random.randint(0, self.N_SEED_BUCKETS - 1)
            logger.debug(f"RL: Exploring with action {action}")
        else:
            # Exploitation: best known action
            if self._llm_bias is not None:
                # Blend Q-values with LLM bias
                blended = self.q_table[self._current_state] + self._llm_bias * 0.3
                action = int(np.argmax(blended))
            else:
                action = int(np.argmax(self.q_table[self._current_state]))
            logger.debug(f"RL: Exploiting with action {action}")

        self._last_action = action
        seed = self._action_to_seed(action)

        # Decay epsilon
        self.epsilon = max(
            self.config.rl_min_epsilon,
            self.epsilon * self.config.rl_epsilon_decay,
        )

        return seed

    def update(self, seed: int, coverage_delta: float, analysis=None):
        """Update Q-table based on observed reward."""
        reward = self._compute_reward(coverage_delta, analysis)
        new_coverage = analysis.coverage_pct if analysis else 0
        new_state = self._coverage_to_state(new_coverage)

        # Q-learning update
        old_q = self.q_table[self._current_state, self._last_action]
        max_future_q = np.max(self.q_table[new_state])
        new_q = old_q + self.lr * (reward + self.gamma * max_future_q - old_q)
        self.q_table[self._current_state, self._last_action] = new_q

        # Record experience
        self._history.append({
            "state": self._current_state,
            "action": self._last_action,
            "reward": reward,
            "next_state": new_state,
            "seed": seed,
            "coverage_delta": coverage_delta,
        })

        self._current_state = new_state
        logger.debug(
            f"RL update: s={self._current_state}, a={self._last_action}, "
            f"r={reward:.3f}, q={new_q:.3f}"
        )

    def _compute_reward(self, coverage_delta: float, analysis=None) -> float:
        """Compute reward signal from coverage improvement."""
        reward = coverage_delta * 10.0  # Scale up for better gradient

        # Bonus for hitting corner cases
        if analysis and hasattr(analysis, "gaps"):
            cross_covered = sum(
                1 for g in analysis.gaps
                if g.coverpoint == "corner_cases" and g.hits > 0
            )
            reward += cross_covered * 2.0

        # Penalty for zero improvement
        if coverage_delta <= 0:
            reward -= 1.0

        return reward

    def incorporate_llm_hint(self, hint: dict):
        """Incorporate LLM-suggested bias into the RL policy."""
        if not hint:
            return

        seeds = hint.get("seeds", [])
        if seeds:
            bias = np.zeros(self.N_SEED_BUCKETS)
            bucket_size = (self.seed_max - self.seed_min) / self.N_SEED_BUCKETS
            for s in seeds:
                bucket = int((s - self.seed_min) / bucket_size)
                bucket = min(max(bucket, 0), self.N_SEED_BUCKETS - 1)
                bias[bucket] += 1.0
            if np.max(bias) > 0:
                bias = bias / np.max(bias)
            self._llm_bias = bias
            logger.info(f"RL: Incorporated LLM bias from {len(seeds)} seed hints")

    def get_stats(self) -> dict:
        """Return RL agent statistics."""
        return {
            "episodes": len(self._history),
            "epsilon": round(self.epsilon, 4),
            "mean_reward": (
                round(np.mean([h["reward"] for h in self._history]), 3)
                if self._history else 0
            ),
            "q_table_nonzero": int(np.count_nonzero(self.q_table)),
        }
