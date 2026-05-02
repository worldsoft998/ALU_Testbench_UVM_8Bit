"""
OpenAI Gymnasium environment for ALU coverage-directed verification.

The agent observes the current coverage state and selects actions that control
stimulus generation parameters (seed region, operand bias, opcode focus,
batch size).  The reward signal drives the agent toward rapid coverage closure.
"""

from __future__ import annotations

from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ai.environments.alu_sim_model import (
    CoverageModel,
    PythonSimRunner,
    StimulusGenerator,
)


class ALUCoverageEnv(gym.Env):
    """
    Gymnasium environment for RL-driven ALU coverage optimization.

    Observation (30-d float32):
        [0:28]  – per-bin covered flag  (0.0 / 1.0)
        [28]    – overall coverage percentage  (0..1)
        [29]    – normalised iteration counter (0..1)

    Action (Discrete 420):
        Encoded as a single integer decomposed into four sub-fields:
            seed_bucket   (0-9)   – selects a seed region
            operand_bias  (0-4)   – default / zeros / ones / boundary / uniform
            opcode_focus  (0-6)   – 0 = uniform, 1-6 = emphasise one opcode
            batch_scale   (0-2)   – small / medium / large batch

    Reward:
        +  coverage_delta * 10    (new bins hit this step)
        +  bonus per newly-covered corner-case bin
        -  small step penalty to encourage efficiency
        +  large bonus when target coverage is reached
    """

    metadata = {"render_modes": ["human"]}

    # Sub-action dimensions
    N_SEED_BUCKETS = 10
    N_OPERAND_BIAS = 5
    N_OPCODE_FOCUS = 7
    N_BATCH_SCALE = 3

    OPERAND_BIAS_MAP = ["default", "zeros", "ones", "boundary", "uniform"]
    BATCH_SIZES = [200, 500, 1000]

    def __init__(
        self,
        target_coverage: float = 95.0,
        max_steps: int = 100,
        base_seed: int = 42,
        transactions_per_step: int = 500,
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        self.target_coverage = target_coverage
        self.max_steps = max_steps
        self.base_seed = base_seed
        self.default_txn_per_step = transactions_per_step
        self.render_mode = render_mode

        obs_dim = CoverageModel.NUM_BINS + 2  # bins + overall_cov + norm_step
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(
            self.N_SEED_BUCKETS
            * self.N_OPERAND_BIAS
            * self.N_OPCODE_FOCUS
            * self.N_BATCH_SCALE
        )

        self._sim: Optional[PythonSimRunner] = None
        self._gen: Optional[StimulusGenerator] = None
        self._step_count = 0
        self._prev_coverage = 0.0
        self._episode_seed = base_seed

    # -- gym API -----------------------------------------------------------

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self._episode_seed = seed
        else:
            self._episode_seed = self.base_seed + (
                self.np_random.integers(0, 100_000) if self.np_random is not None else 0
            )

        self._sim = PythonSimRunner()
        self._gen = StimulusGenerator(seed=self._episode_seed)
        self._step_count = 0
        self._prev_coverage = 0.0

        return self._get_obs(), self._get_info()

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        seed_bucket, op_bias_idx, opcode_focus, batch_idx = self._decode_action(action)

        # Derive concrete parameters from the action
        step_seed = self._episode_seed * 1000 + self._step_count * 10 + seed_bucket
        self._gen.set_seed(step_seed)

        operand_bias = self.OPERAND_BIAS_MAP[op_bias_idx]
        n_txn = self.BATCH_SIZES[batch_idx]

        opcode_weights = [1.0] * 6
        if 1 <= opcode_focus <= 6:
            opcode_weights = [0.5] * 6
            opcode_weights[opcode_focus - 1] = 5.0

        # Generate and simulate
        txns = self._gen.generate_biased(
            n=n_txn, opcode_weights=opcode_weights, operand_bias=operand_bias
        )
        coverage_pct = self._sim.run_batch(txns)

        # Compute reward
        cov_delta = coverage_pct - self._prev_coverage
        reward = cov_delta * 10.0

        # Bonus for newly-covered corner-case bins (indices 16-27)
        corner_vec = self._sim.coverage.covered_vector[16:28]
        corner_bonus = float(np.sum(corner_vec)) * 0.5
        reward += corner_bonus * (1.0 if cov_delta > 0 else 0.0)

        # Step cost
        reward -= 0.1

        # Target-reached bonus
        terminated = coverage_pct >= self.target_coverage
        if terminated:
            reward += 50.0

        self._prev_coverage = coverage_pct
        self._step_count += 1
        truncated = self._step_count >= self.max_steps

        return self._get_obs(), reward, terminated, truncated, self._get_info()

    def render(self) -> None:
        if self.render_mode == "human" and self._sim is not None:
            cov = self._sim.coverage
            print(
                f"Step {self._step_count:3d} | "
                f"Coverage {cov.coverage_percentage:5.1f}% "
                f"({cov.total_covered}/{CoverageModel.NUM_BINS}) | "
                f"Txns {self._sim.total_transactions}"
            )

    # -- helpers -----------------------------------------------------------

    def _decode_action(self, action: int) -> tuple[int, int, int, int]:
        batch_idx = action % self.N_BATCH_SCALE
        action //= self.N_BATCH_SCALE
        opcode_focus = action % self.N_OPCODE_FOCUS
        action //= self.N_OPCODE_FOCUS
        op_bias_idx = action % self.N_OPERAND_BIAS
        action //= self.N_OPERAND_BIAS
        seed_bucket = action % self.N_SEED_BUCKETS
        return seed_bucket, op_bias_idx, opcode_focus, batch_idx

    def _encode_action(
        self, seed_bucket: int, op_bias: int, opcode_focus: int, batch_idx: int
    ) -> int:
        a = seed_bucket
        a = a * self.N_OPERAND_BIAS + op_bias
        a = a * self.N_OPCODE_FOCUS + opcode_focus
        a = a * self.N_BATCH_SCALE + batch_idx
        return a

    def _get_obs(self) -> np.ndarray:
        if self._sim is None:
            return np.zeros(CoverageModel.NUM_BINS + 2, dtype=np.float32)
        state = self._sim.get_coverage_state()
        norm_step = np.array(
            [self._step_count / max(self.max_steps, 1)], dtype=np.float32
        )
        return np.concatenate([state, norm_step])

    def _get_info(self) -> dict[str, Any]:
        if self._sim is None:
            return {}
        return {
            "coverage_pct": self._sim.coverage.coverage_percentage,
            "total_covered": self._sim.coverage.total_covered,
            "total_transactions": self._sim.total_transactions,
            "uncovered_bins": self._sim.coverage.uncovered_bins,
            "step": self._step_count,
        }
