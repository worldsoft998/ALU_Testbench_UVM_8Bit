"""
Bayesian optimization for seed selection.
Uses Gaussian Process to model the seed-to-coverage mapping.
"""

import random
import math
import logging
import numpy as np
from typing import Optional
from ..core.config import MLConfig

logger = logging.getLogger(__name__)


class GaussianProcess:
    """Lightweight Gaussian Process for seed-coverage modeling."""

    def __init__(self, length_scale: float = 1000.0, noise: float = 0.1):
        self.length_scale = length_scale
        self.noise = noise
        self.X = []
        self.y = []

    def _kernel(self, x1: float, x2: float) -> float:
        """RBF (squared exponential) kernel."""
        return math.exp(-0.5 * ((x1 - x2) / self.length_scale) ** 2)

    def fit(self, X: list, y: list):
        """Store training data."""
        self.X = list(X)
        self.y = list(y)

    def predict(self, x: float) -> tuple:
        """Predict mean and variance at point x."""
        if not self.X:
            return 0.0, 1.0

        n = len(self.X)
        K = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                K[i, j] = self._kernel(self.X[i], self.X[j])
            K[i, i] += self.noise ** 2

        k_star = np.array([self._kernel(x, xi) for xi in self.X])
        k_ss = self._kernel(x, x) + self.noise ** 2

        try:
            K_inv = np.linalg.inv(K)
            mu = k_star @ K_inv @ np.array(self.y)
            sigma2 = k_ss - k_star @ K_inv @ k_star
            sigma2 = max(sigma2, 1e-6)
            return float(mu), float(math.sqrt(sigma2))
        except np.linalg.LinAlgError:
            return float(np.mean(self.y)), 1.0


class BayesianSeedOptimizer:
    """
    Bayesian optimization for selecting simulation seeds.
    Models the relationship between seed values and coverage improvement.
    """

    def __init__(self, config: MLConfig):
        self.config = config
        self.gp = GaussianProcess(length_scale=5000.0, noise=0.1)
        self.seed_min = config.seed_range_min
        self.seed_max = config.seed_range_max
        self.xi = config.bayesian_xi
        self.kappa = config.bayesian_kappa
        self.acquisition = config.bayesian_acquisition

        self._observations_x = []
        self._observations_y = []
        self._n_initial = config.bayesian_n_initial
        self._iteration = 0
        self._llm_candidates = []

    def suggest_seed(self) -> int:
        """Suggest the next seed to try using acquisition function."""
        self._iteration += 1

        # Initial random exploration
        if self._iteration <= self._n_initial:
            seed = random.randint(self.seed_min, self.seed_max)
            logger.debug(f"Bayesian: Initial exploration seed={seed}")
            return seed

        # Update GP model
        self.gp.fit(self._observations_x, self._observations_y)

        # Optimize acquisition function over candidate seeds
        candidates = self._generate_candidates()
        best_seed = self.seed_min
        best_acq = -float("inf")

        for c in candidates:
            acq = self._acquisition_function(c)
            if acq > best_acq:
                best_acq = acq
                best_seed = c

        logger.debug(f"Bayesian: Selected seed={best_seed} (acq={best_acq:.4f})")
        return best_seed

    def update(self, seed: int, coverage_delta: float, analysis=None):
        """Record observation of seed -> coverage_delta."""
        self._observations_x.append(float(seed))
        self._observations_y.append(float(coverage_delta))
        logger.debug(
            f"Bayesian: Recorded seed={seed}, delta={coverage_delta:.4f} "
            f"(n={len(self._observations_x)})"
        )

    def incorporate_llm_hint(self, hint: dict):
        """Incorporate LLM-suggested seeds as candidates."""
        seeds = hint.get("seeds", [])
        if seeds:
            self._llm_candidates = [int(s) for s in seeds]
            logger.info(f"Bayesian: Added {len(seeds)} LLM candidate seeds")

    def _generate_candidates(self, n: int = 200) -> list:
        """Generate candidate seeds to evaluate."""
        candidates = []

        # Random candidates
        candidates.extend([
            random.randint(self.seed_min, self.seed_max) for _ in range(n)
        ])

        # Candidates near previously good seeds
        if self._observations_x:
            sorted_obs = sorted(
                zip(self._observations_x, self._observations_y),
                key=lambda x: x[1],
                reverse=True,
            )
            for x, _ in sorted_obs[:5]:
                for delta in [-1000, -500, -100, 100, 500, 1000]:
                    c = int(x + delta)
                    if self.seed_min <= c <= self.seed_max:
                        candidates.append(c)

        # LLM-suggested candidates
        candidates.extend(self._llm_candidates)

        return candidates

    def _acquisition_function(self, x: float) -> float:
        """Compute acquisition function value."""
        mu, sigma = self.gp.predict(x)

        if self.acquisition == "ei":
            return self._expected_improvement(mu, sigma)
        elif self.acquisition == "ucb":
            return mu + self.kappa * sigma
        elif self.acquisition == "pi":
            return self._probability_of_improvement(mu, sigma)
        else:
            return self._expected_improvement(mu, sigma)

    def _expected_improvement(self, mu: float, sigma: float) -> float:
        """Expected Improvement acquisition function."""
        if sigma <= 0:
            return 0.0
        if not self._observations_y:
            return mu
        best_y = max(self._observations_y)
        z = (mu - best_y - self.xi) / sigma
        # Approximation of EI using standard normal
        return sigma * (z * self._norm_cdf(z) + self._norm_pdf(z))

    def _probability_of_improvement(self, mu: float, sigma: float) -> float:
        """Probability of Improvement acquisition function."""
        if sigma <= 0:
            return 0.0
        if not self._observations_y:
            return 0.5
        best_y = max(self._observations_y)
        z = (mu - best_y - self.xi) / sigma
        return self._norm_cdf(z)

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    def get_stats(self) -> dict:
        """Return optimizer statistics."""
        return {
            "observations": len(self._observations_x),
            "best_seed": (
                int(self._observations_x[np.argmax(self._observations_y)])
                if self._observations_y else None
            ),
            "best_delta": (
                round(max(self._observations_y), 4)
                if self._observations_y else 0
            ),
            "acquisition": self.acquisition,
        }
