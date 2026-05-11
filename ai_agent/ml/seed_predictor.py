"""
ML-based seed prediction using Random Forest and ensemble methods.
Predicts which seeds are most likely to improve coverage.
"""

import random
import logging
import numpy as np
from typing import Optional
from ..core.config import MLConfig

logger = logging.getLogger(__name__)


class SeedPredictor:
    """
    Random Forest-based seed predictor.
    Learns from historical seed->coverage_delta mappings.
    """

    def __init__(self, config: MLConfig):
        self.config = config
        self.seed_min = config.seed_range_min
        self.seed_max = config.seed_range_max
        self._model = None
        self._X = []
        self._y = []
        self._min_samples = 10
        self._llm_candidates = []
        self._init_model()

    def _init_model(self):
        """Initialize the Random Forest model."""
        try:
            from sklearn.ensemble import RandomForestRegressor
            self._model = RandomForestRegressor(
                n_estimators=50,
                max_depth=8,
                random_state=42,
                n_jobs=-1,
            )
        except ImportError:
            logger.warning(
                "scikit-learn not installed. Using fallback predictor. "
                "Install with: pip install scikit-learn"
            )

    def _seed_to_features(self, seed: int) -> list:
        """Extract features from a seed value."""
        return [
            seed,
            seed % 7,     # Modular pattern (related to opcode count + 1)
            seed % 256,   # Low byte pattern
            seed % 65536, # Two-byte pattern
            seed // 1000, # Thousands bucket
            (seed * 2654435761) % (2**32),  # Hash spread
        ]

    def suggest_seed(self) -> int:
        """Predict the best seed to try next."""
        if self._model is None or len(self._X) < self._min_samples:
            return self._smart_random_seed()

        # Retrain model
        X = np.array([self._seed_to_features(s) for s in self._X])
        y = np.array(self._y)
        try:
            self._model.fit(X, y)
        except Exception:
            return self._smart_random_seed()

        # Generate candidates and predict
        candidates = self._generate_candidates(500)
        X_candidates = np.array([self._seed_to_features(c) for c in candidates])
        predictions = self._model.predict(X_candidates)

        best_idx = np.argmax(predictions)
        seed = candidates[best_idx]
        logger.debug(
            f"RF predictor: seed={seed}, predicted_delta={predictions[best_idx]:.4f}"
        )
        return seed

    def update(self, seed: int, coverage_delta: float, analysis=None):
        """Record a new observation."""
        self._X.append(seed)
        self._y.append(coverage_delta)

    def incorporate_llm_hint(self, hint: dict):
        """Store LLM-suggested seeds."""
        seeds = hint.get("seeds", [])
        if seeds:
            self._llm_candidates = [int(s) for s in seeds]

    def _generate_candidates(self, n: int = 500) -> list:
        """Generate candidate seeds."""
        candidates = [
            random.randint(self.seed_min, self.seed_max) for _ in range(n)
        ]
        candidates.extend(self._llm_candidates)

        # Add seeds near historically good ones
        if self._y:
            top_indices = np.argsort(self._y)[-5:]
            for idx in top_indices:
                base_seed = self._X[idx]
                for delta in range(-2000, 2001, 200):
                    c = base_seed + delta
                    if self.seed_min <= c <= self.seed_max:
                        candidates.append(c)
        return candidates

    def _smart_random_seed(self) -> int:
        """Generate a seed using heuristics before enough data exists."""
        used = set(self._X)
        for _ in range(100):
            seed = random.randint(self.seed_min, self.seed_max)
            if seed not in used:
                return seed
        return random.randint(self.seed_min, self.seed_max)

    def get_stats(self) -> dict:
        return {
            "training_samples": len(self._X),
            "model_type": "RandomForest",
            "has_model": self._model is not None,
        }


class EnsembleOptimizer:
    """
    Ensemble optimizer combining multiple ML strategies.
    Aggregates suggestions from RL, Bayesian, and RF predictors.
    """

    def __init__(self, config: MLConfig):
        self.config = config
        from .rl_agent import RLSeedAgent
        from .bayesian_opt import BayesianSeedOptimizer

        self._rl = RLSeedAgent(config)
        self._bayesian = BayesianSeedOptimizer(config)
        self._rf = SeedPredictor(config)
        self._weights = [0.3, 0.4, 0.3]  # RL, Bayesian, RF
        self._iteration = 0

    def suggest_seed(self) -> int:
        """Weighted ensemble seed suggestion."""
        self._iteration += 1

        candidates = []
        try:
            candidates.append((self._rl.suggest_seed(), self._weights[0]))
        except Exception:
            pass
        try:
            candidates.append((self._bayesian.suggest_seed(), self._weights[1]))
        except Exception:
            pass
        try:
            candidates.append((self._rf.suggest_seed(), self._weights[2]))
        except Exception:
            pass

        if not candidates:
            return random.randint(self.config.seed_range_min, self.config.seed_range_max)

        # Select seed with highest weight
        candidates.sort(key=lambda x: x[1], reverse=True)
        seed = candidates[0][0]

        # Occasionally pick from other models for diversity
        if random.random() < 0.3 and len(candidates) > 1:
            seed = random.choice(candidates)[0]

        return seed

    def update(self, seed: int, coverage_delta: float, analysis=None):
        """Update all sub-models."""
        self._rl.update(seed, coverage_delta, analysis)
        self._bayesian.update(seed, coverage_delta, analysis)
        self._rf.update(seed, coverage_delta, analysis)

    def incorporate_llm_hint(self, hint: dict):
        """Forward LLM hints to all sub-models."""
        self._rl.incorporate_llm_hint(hint)
        self._bayesian.incorporate_llm_hint(hint)
        self._rf.incorporate_llm_hint(hint)

    def get_stats(self) -> dict:
        return {
            "iteration": self._iteration,
            "rl_stats": self._rl.get_stats(),
            "bayesian_stats": self._bayesian.get_stats(),
            "rf_stats": self._rf.get_stats(),
        }
