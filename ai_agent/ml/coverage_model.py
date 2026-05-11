"""
Coverage prediction model.
Predicts expected coverage after a simulation run with given parameters.
"""

import logging
import numpy as np
from typing import Optional
from ..core.config import MLConfig

logger = logging.getLogger(__name__)


class CoveragePredictor:
    """
    Neural network-based coverage predictor.
    Learns to predict coverage improvement from simulation parameters.
    """

    def __init__(self, config: MLConfig):
        self.config = config
        self.input_dim = 8  # seed features + current coverage state
        self.hidden_dim = 32
        self.output_dim = 1
        self._lr = 0.001

        # Simple two-layer network weights
        np.random.seed(42)
        self.W1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b1 = np.zeros(self.hidden_dim)
        self.W2 = np.random.randn(self.hidden_dim, self.output_dim) * 0.1
        self.b2 = np.zeros(self.output_dim)

        self._X_history = []
        self._y_history = []

    def predict(self, seed: int, current_coverage: float, num_items: int,
                uncovered_bins: int = 0) -> float:
        """Predict coverage improvement for given parameters."""
        features = self._extract_features(seed, current_coverage, num_items, uncovered_bins)
        return float(self._forward(features))

    def train_step(self, seed: int, current_coverage: float, num_items: int,
                   actual_delta: float, uncovered_bins: int = 0):
        """Train on a single observation."""
        features = self._extract_features(seed, current_coverage, num_items, uncovered_bins)
        self._X_history.append(features)
        self._y_history.append(actual_delta)

        # Forward pass
        pred = self._forward(features)
        error = actual_delta - pred

        # Backward pass (simple gradient descent)
        self._backward(features, error)

    def batch_train(self, n_epochs: int = 10):
        """Train on all accumulated history."""
        if len(self._X_history) < 5:
            return

        X = np.array(self._X_history)
        y = np.array(self._y_history)

        for _ in range(n_epochs):
            indices = np.random.permutation(len(X))
            for i in indices:
                pred = self._forward(X[i])
                error = y[i] - pred
                self._backward(X[i], error)

    def _extract_features(self, seed: int, current_coverage: float,
                          num_items: int, uncovered_bins: int) -> np.ndarray:
        """Extract feature vector."""
        return np.array([
            seed / 100000.0,
            (seed % 256) / 255.0,
            (seed % 7) / 6.0,
            current_coverage / 100.0,
            num_items / 80000.0,
            uncovered_bins / 30.0,
            1.0 - (current_coverage / 100.0),  # Remaining gap
            min(1.0, uncovered_bins / 10.0),    # Gap urgency
        ])

    def _forward(self, x: np.ndarray) -> float:
        """Forward pass through network."""
        h = np.tanh(x @ self.W1 + self.b1)
        out = h @ self.W2 + self.b2
        return float(out[0])

    def _backward(self, x: np.ndarray, error: float):
        """Backward pass with gradient descent."""
        h = np.tanh(x @ self.W1 + self.b1)

        # Output layer gradients
        d_out = np.array([error])
        self.W2 += self._lr * np.outer(h, d_out)
        self.b2 += self._lr * d_out

        # Hidden layer gradients
        d_h = d_out @ self.W2.T * (1 - h ** 2)
        self.W1 += self._lr * np.outer(x, d_h)
        self.b1 += self._lr * d_h

    def get_stats(self) -> dict:
        return {
            "training_samples": len(self._X_history),
            "architecture": f"{self.input_dim}-{self.hidden_dim}-{self.output_dim}",
        }
