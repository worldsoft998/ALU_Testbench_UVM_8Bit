"""Gymnasium env that uses a Python reference model of the ALU.

The agent picks a stimulus tuple (op, A, B, Cin) and receives reward based on
*new* coverage bins hit. The observation is a flat hit-mask plus the current
coverage fraction - a small, stable state the policies can easily shape.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .alu_model import AluInputs, alu_model
from .coverage_model import CoverageModel


# Action encoding: one MultiDiscrete for (op, A, B, Cin, Reset)
_OP_VALUES = 6          # 0..5
_A_VALUES = 256
_B_VALUES = 256
_CIN_VALUES = 2
_RESET_VALUES = 2


class AluCoverageEnv(gym.Env):
    """Offline training env. Step == one stimulus + DUT response."""

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        max_steps: int = 1000,
        novelty_bonus: float = 1.0,
        redundancy_penalty: float = -0.01,
        target_coverage: float = 100.0,
    ) -> None:
        super().__init__()
        self.max_steps = int(max_steps)
        self.novelty_bonus = float(novelty_bonus)
        self.redundancy_penalty = float(redundancy_penalty)
        self.target_coverage = float(target_coverage)

        self._cov = CoverageModel()

        self.action_space = spaces.MultiDiscrete(
            [_OP_VALUES, _A_VALUES, _B_VALUES, _CIN_VALUES, _RESET_VALUES]
        )
        # Observation: hit mask (N bins) + coverage fraction + step progress
        n_bins = self._cov.total_bins
        low = np.zeros(n_bins + 2, dtype=np.float32)
        high = np.concatenate(
            [np.ones(n_bins, dtype=np.float32), np.array([1.0, 1.0], dtype=np.float32)]
        )
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

        self._step_idx = 0
        self._cumulative_new = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _obs(self) -> np.ndarray:
        mask = np.asarray(self._cov.hit_mask(), dtype=np.float32)
        cov = np.float32(self._cov.coverage / 100.0)
        progress = np.float32(self._step_idx / max(1, self.max_steps))
        return np.concatenate([mask, np.array([cov, progress], dtype=np.float32)])

    # ------------------------------------------------------------------
    # Gym API
    # ------------------------------------------------------------------
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self._cov = CoverageModel()
        self._step_idx = 0
        self._cumulative_new = 0
        return self._obs(), {"coverage_pct": 0.0}

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        op, a, b, cin, rst = (int(x) for x in action)
        op %= _OP_VALUES
        inp = AluInputs(a=a, b=b, op=op, c_in=cin, reset=rst)
        _ = alu_model(inp)  # run the reference model for side-effect parity
        new_hits = self._cov.sample(reset=inp.reset, c_in=inp.c_in, op=inp.op,
                                    a=inp.a, b=inp.b)

        self._cumulative_new += new_hits
        self._step_idx += 1

        reward = self.novelty_bonus * new_hits
        if new_hits == 0:
            reward += self.redundancy_penalty

        terminated = self._cov.coverage >= self.target_coverage
        truncated = self._step_idx >= self.max_steps

        info = {
            "coverage_pct": self._cov.coverage,
            "hit_bins": self._cov.hit_bins,
            "total_bins": self._cov.total_bins,
            "new_bins": new_hits,
            "from_rl": True,
        }
        return self._obs(), float(reward), bool(terminated), bool(truncated), info

    def render(self) -> str:
        return (
            f"step={self._step_idx}/{self.max_steps} "
            f"cov={self._cov.coverage:.2f}% "
            f"hit={self._cov.hit_bins}/{self._cov.total_bins}"
        )

    @property
    def coverage_model(self) -> CoverageModel:
        return self._cov
