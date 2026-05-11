"""Tests for ML seed prediction and optimization models."""

import pytest
import numpy as np
from ai_agent.core.config import MLConfig
from ai_agent.ml.rl_agent import RLSeedAgent
from ai_agent.ml.bayesian_opt import BayesianSeedOptimizer, GaussianProcess
from ai_agent.ml.seed_predictor import SeedPredictor, EnsembleOptimizer
from ai_agent.ml.coverage_model import CoveragePredictor


class TestRLSeedAgent:
    def setup_method(self):
        self.config = MLConfig()
        self.agent = RLSeedAgent(self.config)

    def test_suggest_seed_in_range(self):
        seed = self.agent.suggest_seed()
        assert self.config.seed_range_min <= seed <= self.config.seed_range_max

    def test_update(self):
        seed = self.agent.suggest_seed()
        self.agent.update(seed, 5.0)
        stats = self.agent.get_stats()
        assert stats["episodes"] == 1

    def test_epsilon_decay(self):
        initial_eps = self.agent.epsilon
        for _ in range(10):
            self.agent.suggest_seed()
        assert self.agent.epsilon < initial_eps

    def test_incorporate_llm_hint(self):
        hint = {"seeds": [42, 1000, 50000]}
        self.agent.incorporate_llm_hint(hint)
        assert self.agent._llm_bias is not None


class TestBayesianOptimizer:
    def setup_method(self):
        self.config = MLConfig()
        self.config.bayesian_n_initial = 3
        self.optimizer = BayesianSeedOptimizer(self.config)

    def test_suggest_seed_in_range(self):
        seed = self.optimizer.suggest_seed()
        assert self.config.seed_range_min <= seed <= self.config.seed_range_max

    def test_update_and_suggest(self):
        for i in range(5):
            seed = self.optimizer.suggest_seed()
            self.optimizer.update(seed, float(i) * 0.5)
        stats = self.optimizer.get_stats()
        assert stats["observations"] == 5

    def test_incorporate_llm_hint(self):
        hint = {"seeds": [42, 1000]}
        self.optimizer.incorporate_llm_hint(hint)
        assert len(self.optimizer._llm_candidates) == 2


class TestGaussianProcess:
    def test_predict_with_no_data(self):
        gp = GaussianProcess()
        mu, sigma = gp.predict(50.0)
        assert mu == 0.0
        assert sigma == 1.0

    def test_predict_with_data(self):
        gp = GaussianProcess(length_scale=100.0)
        gp.fit([10.0, 20.0, 30.0], [1.0, 2.0, 3.0])
        mu, sigma = gp.predict(15.0)
        assert 0.5 < mu < 2.5


class TestSeedPredictor:
    def test_smart_random_seed(self):
        config = MLConfig()
        predictor = SeedPredictor(config)
        seed = predictor.suggest_seed()
        assert config.seed_range_min <= seed <= config.seed_range_max

    def test_update(self):
        config = MLConfig()
        predictor = SeedPredictor(config)
        predictor.update(42, 1.5)
        assert predictor.get_stats()["training_samples"] == 1


class TestEnsembleOptimizer:
    def test_suggest_seed(self):
        config = MLConfig()
        ensemble = EnsembleOptimizer(config)
        seed = ensemble.suggest_seed()
        assert config.seed_range_min <= seed <= config.seed_range_max

    def test_update_all_models(self):
        config = MLConfig()
        ensemble = EnsembleOptimizer(config)
        seed = ensemble.suggest_seed()
        ensemble.update(seed, 2.0)
        stats = ensemble.get_stats()
        assert stats["rl_stats"]["episodes"] == 1
        assert stats["bayesian_stats"]["observations"] == 1


class TestCoveragePredictor:
    def test_predict(self):
        config = MLConfig()
        predictor = CoveragePredictor(config)
        pred = predictor.predict(seed=42, current_coverage=50.0, num_items=5000)
        assert isinstance(pred, float)

    def test_train_step(self):
        config = MLConfig()
        predictor = CoveragePredictor(config)
        predictor.train_step(42, 50.0, 5000, 2.5)
        assert predictor.get_stats()["training_samples"] == 1

    def test_batch_train(self):
        config = MLConfig()
        predictor = CoveragePredictor(config)
        for i in range(10):
            predictor.train_step(i * 1000, float(i * 10), 5000, float(i) * 0.5)
        predictor.batch_train(n_epochs=3)
        assert predictor.get_stats()["training_samples"] == 10
