"""
Seed generation and management.
Provides intelligent seed generation strategies when ML models are unavailable.
"""

import random
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SeedManager:
    """Manages simulation seed generation with various strategies."""

    # Known-good seed families for ALU verification
    # These are derived from analysis of typical ALU coverage patterns
    CORNER_CASE_SEEDS = [
        42, 137, 255, 1024, 4096, 8192, 16384, 32768, 65535,
        7, 13, 31, 127, 257, 997, 2039, 4093, 8191, 16381,
    ]

    def __init__(self, config):
        self.config = config
        self.seed_min = config.ml.seed_range_min
        self.seed_max = config.ml.seed_range_max
        self._used_seeds = set()
        self._seed_scores = {}

    def generate_smart_seed(self, used_seeds: list = None,
                            coverage_trend: list = None) -> int:
        """Generate a seed using heuristics."""
        used = set(used_seeds or []) | self._used_seeds

        # Strategy 1: If coverage is stagnating, try corner case seeds
        if coverage_trend and len(coverage_trend) >= 3:
            recent = coverage_trend[-3:]
            delta = max(recent) - min(recent)
            if delta < 0.5:  # Stagnation
                for s in self.CORNER_CASE_SEEDS:
                    if s not in used:
                        self._used_seeds.add(s)
                        return s

        # Strategy 2: Hash-based diverse seeds
        seed = self._hash_based_seed(len(used))
        attempts = 0
        while seed in used and attempts < 100:
            attempts += 1
            seed = self._hash_based_seed(len(used) + attempts)

        self._used_seeds.add(seed)
        return seed

    def generate_random_seed(self) -> int:
        """Generate a purely random seed."""
        seed = random.randint(self.seed_min, self.seed_max)
        while seed in self._used_seeds:
            seed = random.randint(self.seed_min, self.seed_max)
        self._used_seeds.add(seed)
        return seed

    def generate_sequential_seeds(self, n: int, start: int = 1) -> list:
        """Generate a sequence of evenly-spaced seeds."""
        step = (self.seed_max - self.seed_min) // max(n, 1)
        seeds = []
        for i in range(n):
            s = start + i * step
            if s > self.seed_max:
                s = s % self.seed_max + self.seed_min
            seeds.append(s)
            self._used_seeds.add(s)
        return seeds

    def record_seed_result(self, seed: int, coverage_delta: float):
        """Record the coverage delta achieved by a seed."""
        self._seed_scores[seed] = coverage_delta
        self._used_seeds.add(seed)

    def get_top_seeds(self, n: int = 5) -> list:
        """Return the top N seeds by coverage improvement."""
        sorted_seeds = sorted(
            self._seed_scores.items(), key=lambda x: x[1], reverse=True
        )
        return [s for s, _ in sorted_seeds[:n]]

    def _hash_based_seed(self, index: int) -> int:
        """Generate a well-distributed seed using hashing."""
        h = hashlib.md5(f"aivo_seed_{index}".encode()).hexdigest()
        seed = int(h[:8], 16) % (self.seed_max - self.seed_min) + self.seed_min
        return seed

    def get_stats(self) -> dict:
        return {
            "total_seeds_used": len(self._used_seeds),
            "scored_seeds": len(self._seed_scores),
            "top_5": self.get_top_seeds(5),
        }
