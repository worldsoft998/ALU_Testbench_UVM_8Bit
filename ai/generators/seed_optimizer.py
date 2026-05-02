"""
Seed optimisation engine.

Maintains a history of seed → coverage-gain mappings and uses RL-derived
insights plus heuristic gap analysis to propose seeds that are most likely
to increase functional coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ai.environments.alu_sim_model import CoverageModel


@dataclass
class SeedRecord:
    seed: int
    coverage_before: float
    coverage_after: float
    new_bins_hit: int
    transactions: int

    @property
    def gain(self) -> float:
        return self.coverage_after - self.coverage_before


class SeedOptimizer:
    """
    Tracks seed performance history and recommends seeds targeting uncovered
    functional coverage bins.

    Strategy layers (applied in priority order):
        1. **Gap-targeted** – deterministic seeds crafted to hit specific
           uncovered corner-case bins.
        2. **Replay-best** – re-use seed families that previously produced
           high coverage gain.
        3. **Exploration** – random seeds from under-explored regions.
    """

    def __init__(self, base_seed: int = 42):
        self.base_seed = base_seed
        self.history: list[SeedRecord] = []
        self._rng = np.random.RandomState(base_seed)

    def record(self, rec: SeedRecord) -> None:
        self.history.append(rec)

    def suggest_seeds(
        self,
        n: int,
        coverage: CoverageModel,
        strategy: str = "auto",
    ) -> list[int]:
        """Return *n* seeds ranked by expected coverage contribution."""
        if strategy == "gap_targeted":
            return self._gap_targeted_seeds(n, coverage)
        elif strategy == "replay_best":
            return self._replay_best_seeds(n)
        elif strategy == "exploration":
            return self._exploration_seeds(n)
        else:
            # auto: mix strategies
            gap = self._gap_targeted_seeds(max(1, n // 3), coverage)
            replay = self._replay_best_seeds(max(1, n // 3))
            explore = self._exploration_seeds(n - len(gap) - len(replay))
            return gap + replay + explore

    def suggest_opcode_weights(self, coverage: CoverageModel) -> list[float]:
        """Produce opcode weights that emphasise under-covered opcodes."""
        weights = [1.0] * 6
        uncovered = coverage.uncovered_indices
        for idx in uncovered:
            if 6 <= idx <= 11:
                weights[idx - 6] += 4.0
            if 16 <= idx <= 27:
                op_idx = (idx - 16) // 2
                weights[op_idx] += 3.0
        total = sum(weights)
        return [w / total for w in weights]

    def suggest_operand_bias(self, coverage: CoverageModel) -> str:
        uncovered = set(coverage.uncovered_bins)
        needs_zeros = any("Zeros" in b or "cross2" in b for b in uncovered)
        needs_ones = any("Ones" in b or "cross1" in b for b in uncovered)
        if needs_zeros and needs_ones:
            return "boundary"
        if needs_zeros:
            return "zeros"
        if needs_ones:
            return "ones"
        return "default"

    # -- internal strategies -----------------------------------------------

    def _gap_targeted_seeds(self, n: int, coverage: CoverageModel) -> list[int]:
        seeds = []
        for idx in coverage.uncovered_indices[:n]:
            seeds.append(self.base_seed * 100 + idx * 7 + len(self.history))
        while len(seeds) < n:
            seeds.append(int(self._rng.randint(0, 2**31)))
        return seeds[:n]

    def _replay_best_seeds(self, n: int) -> list[int]:
        if not self.history:
            return self._exploration_seeds(n)
        sorted_hist = sorted(self.history, key=lambda r: r.gain, reverse=True)
        base_seeds = [r.seed for r in sorted_hist[:n]]
        return [s + len(self.history) for s in base_seeds][:n]

    def _exploration_seeds(self, n: int) -> list[int]:
        used = {r.seed for r in self.history}
        seeds = []
        while len(seeds) < n:
            s = int(self._rng.randint(0, 2**31))
            if s not in used:
                seeds.append(s)
        return seeds
