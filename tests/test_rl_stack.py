#!/usr/bin/env python3
"""
Integration test for the complete RL/ML stack.
Tests the full pipeline: config -> optimizer -> seed suggestion -> update -> convergence.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_agent.core.config import AgentConfig, MLConfig
from ai_agent.core.coverage_parser import (
    CoverageParser, CoverageReport, CoverageBin, Coverpoint, CrossCoverage,
)
from ai_agent.core.gap_analyzer import GapAnalyzer
from ai_agent.ml.rl_agent import RLSeedAgent
from ai_agent.ml.bayesian_opt import BayesianSeedOptimizer
from ai_agent.ml.seed_predictor import SeedPredictor, EnsembleOptimizer
from ai_agent.ml.coverage_model import CoveragePredictor
from ai_agent.simulation.seed_manager import SeedManager
from ai_agent.comparison.metrics import MetricsCollector


def test_config_loading():
    """Test configuration creation and validation."""
    config = AgentConfig()
    warnings = config.validate()
    assert isinstance(warnings, list)
    print("[PASS] Config loading and validation")


def test_coverage_parser_empty_report():
    """Test creating an empty ALU coverage report."""
    parser = CoverageParser()
    report = parser.create_empty_alu_report()
    assert "op_code" in report.coverpoints
    assert "corner_cases" in report.crosses
    assert len(report.crosses["corner_cases"].bins) == 12
    print("[PASS] Coverage parser empty report")


def test_gap_analyzer():
    """Test gap analysis on a partial coverage report."""
    parser = CoverageParser()
    report = parser.create_empty_alu_report()
    # Mark some bins as covered
    report.coverpoints["op_code"].bins[0].is_covered = True
    report.coverpoints["op_code"].bins[0].hits = 10
    report.compute_overall()

    analyzer = GapAnalyzer()
    analysis = analyzer.analyze(report)
    assert analysis.total_uncovered > 0
    assert len(analysis.gaps) > 0
    print(f"[PASS] Gap analyzer: {analysis.total_uncovered} uncovered bins")


def test_rl_agent_loop():
    """Test RL agent seed suggestion and learning loop."""
    config = MLConfig()
    agent = RLSeedAgent(config)

    for i in range(10):
        seed = agent.suggest_seed()
        assert config.seed_range_min <= seed <= config.seed_range_max
        reward = max(0, 5.0 - i * 0.3)
        agent.update(seed, reward)

    stats = agent.get_stats()
    assert stats["episodes"] == 10
    assert stats["epsilon"] < config.rl_epsilon
    print(f"[PASS] RL agent: {stats['episodes']} episodes, eps={stats['epsilon']:.4f}")


def test_bayesian_optimizer_loop():
    """Test Bayesian optimization loop."""
    config = MLConfig()
    config.bayesian_n_initial = 3
    optimizer = BayesianSeedOptimizer(config)

    for i in range(8):
        seed = optimizer.suggest_seed()
        delta = max(0, 3.0 - i * 0.2)
        optimizer.update(seed, delta)

    stats = optimizer.get_stats()
    assert stats["observations"] == 8
    print(f"[PASS] Bayesian optimizer: {stats['observations']} observations")


def test_seed_manager():
    """Test seed manager smart generation."""
    config = AgentConfig()
    mgr = SeedManager(config)

    seeds = set()
    for _ in range(20):
        s = mgr.generate_smart_seed(used_seeds=list(seeds))
        assert s not in seeds
        seeds.add(s)

    stats = mgr.get_stats()
    assert stats["total_seeds_used"] >= 20
    print(f"[PASS] Seed manager: {stats['total_seeds_used']} unique seeds")


def test_metrics_collector():
    """Test metrics collection and comparison."""
    ai_metrics = MetricsCollector()
    bl_metrics = MetricsCollector()

    for i in range(10):
        ai_metrics.record_iteration(i + 1, i * 1000, "ai", (i + 1) * 10.0, 10 - i, 1.0)
        bl_metrics.record_iteration(i + 1, i * 2000, "baseline", (i + 1) * 8.0, 12 - i, 1.2)

    comparison = ai_metrics.compute_comparison(bl_metrics)
    assert comparison["ai_final_coverage"] > comparison["baseline_final_coverage"]
    print(f"[PASS] Metrics: AI={comparison['ai_final_coverage']:.1f}% vs "
          f"Baseline={comparison['baseline_final_coverage']:.1f}%")


def test_coverage_predictor():
    """Test neural network coverage predictor."""
    config = MLConfig()
    predictor = CoveragePredictor(config)

    for i in range(15):
        seed = i * 5000
        cov = float(i * 5)
        delta = max(0, 3.0 - i * 0.1)
        predictor.train_step(seed, cov, 5000, delta)

    predictor.batch_train(n_epochs=5)

    pred = predictor.predict(seed=25000, current_coverage=50.0, num_items=5000)
    assert isinstance(pred, float)
    print(f"[PASS] Coverage predictor: prediction={pred:.4f}")


def test_ensemble_optimizer():
    """Test ensemble optimizer combining all methods."""
    config = MLConfig()
    config.bayesian_n_initial = 2
    ensemble = EnsembleOptimizer(config)

    for i in range(5):
        seed = ensemble.suggest_seed()
        ensemble.update(seed, max(0, 2.0 - i * 0.3))

    stats = ensemble.get_stats()
    assert stats["iteration"] == 5
    print(f"[PASS] Ensemble optimizer: {stats['iteration']} iterations")


def test_full_pipeline():
    """Integration test: full pipeline from config to gap analysis."""
    config = AgentConfig()
    parser = CoverageParser()
    analyzer = GapAnalyzer()
    seed_mgr = SeedManager(config)
    metrics = MetricsCollector()

    # Simulate multi-iteration verification loop
    all_reports = []
    for i in range(5):
        seed = seed_mgr.generate_smart_seed(
            used_seeds=[r.seed for r in all_reports]
        )

        # Simulate coverage report (progressively covering more bins)
        report = parser.create_empty_alu_report()
        report.seed = seed
        report.iteration = i + 1

        # Progressively cover bins
        for cp in report.coverpoints.values():
            for j, b in enumerate(cp.bins):
                if j <= i:
                    b.is_covered = True
                    b.hits = 10
        for cr in report.crosses.values():
            for j, b in enumerate(cr.bins):
                if j <= i * 2:
                    b.is_covered = True
                    b.hits = 5

        report.compute_overall()
        all_reports.append(report)

        merged = parser.merge_reports(all_reports)
        analysis = analyzer.analyze(merged)

        metrics.record_iteration(
            i + 1, seed, "ai", merged.overall_coverage, analysis.total_uncovered, 1.0
        )

    trend = metrics.get_coverage_trend()
    assert trend[-1] > trend[0]
    print(f"[PASS] Full pipeline: coverage {trend[0]:.1f}% -> {trend[-1]:.1f}%")


def main():
    """Run all tests."""
    print("=" * 60)
    print("AIa-VO: RL/ML Stack Integration Tests")
    print("=" * 60)

    tests = [
        test_config_loading,
        test_coverage_parser_empty_report,
        test_gap_analyzer,
        test_rl_agent_loop,
        test_bayesian_optimizer_loop,
        test_seed_manager,
        test_metrics_collector,
        test_coverage_predictor,
        test_ensemble_optimizer,
        test_full_pipeline,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test_fn.__name__}: {e}")
            failed += 1

    print("")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
