"""
Main AI Verification Agent orchestrator.
Coordinates simulation runs, coverage analysis, LLM consultation, and ML optimization.
"""

import os
import json
import time
import logging
from typing import Optional

from .config import AgentConfig
from .coverage_parser import CoverageParser, CoverageReport
from .gap_analyzer import GapAnalyzer, GapAnalysis
from ..simulation.vcs_runner import VCSRunner
from ..simulation.seed_manager import SeedManager
from ..simulation.results_db import ResultsDB
from ..simulation.log_monitor import LogMonitor
from ..comparison.metrics import MetricsCollector
from ..comparison.report_gen import ReportGenerator

logger = logging.getLogger(__name__)


class AIVerificationAgent:
    """
    Top-level AI agent that orchestrates verification acceleration.

    Operates at the simulation boundary without modifying existing testbenches.
    Uses VCS plusargs (+ntb_random_seed) to control randomization and parses
    coverage reports to drive intelligent seed selection.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.parser = CoverageParser(config.project_root)
        self.analyzer = GapAnalyzer()
        self.runner = VCSRunner(config)
        self.seed_mgr = SeedManager(config)
        self.results_db = ResultsDB(config)
        self.log_monitor = LogMonitor(config)
        self.metrics = MetricsCollector()
        self.report_gen = ReportGenerator(config)

        self._llm_client = None
        self._ml_optimizer = None
        self._iteration = 0
        self._cumulative_report: Optional[CoverageReport] = None
        self._all_reports: list = []
        self._converge_count = 0

        self._init_components()

    def _init_components(self):
        """Initialize LLM and ML components based on config."""
        if self.config.enable_llm:
            try:
                self._llm_client = self._create_llm_client()
                logger.info(f"LLM client initialized: {self.config.llm.provider}")
            except Exception as e:
                logger.warning(f"LLM initialization failed: {e}. Continuing without LLM.")
                self._llm_client = None

        if self.config.enable_ml:
            try:
                self._ml_optimizer = self._create_ml_optimizer()
                logger.info(f"ML optimizer initialized: {self.config.ml.algorithm}")
            except Exception as e:
                logger.warning(f"ML initialization failed: {e}. Continuing without ML.")
                self._ml_optimizer = None

    def _create_llm_client(self):
        """Create LLM client based on config."""
        provider = self.config.llm.provider.lower()
        if provider == "openai":
            from ..llm.openai_client import OpenAIClient
            return OpenAIClient(self.config.llm)
        elif provider == "gemini":
            from ..llm.gemini_client import GeminiClient
            return GeminiClient(self.config.llm)
        elif provider == "claude":
            from ..llm.claude_client import ClaudeClient
            return ClaudeClient(self.config.llm)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _create_ml_optimizer(self):
        """Create ML optimizer based on config."""
        algo = self.config.ml.algorithm.lower()
        if algo == "bayesian":
            from ..ml.bayesian_opt import BayesianSeedOptimizer
            return BayesianSeedOptimizer(self.config.ml)
        elif algo == "rl":
            from ..ml.rl_agent import RLSeedAgent
            return RLSeedAgent(self.config.ml)
        elif algo == "random_forest":
            from ..ml.seed_predictor import SeedPredictor
            return SeedPredictor(self.config.ml)
        elif algo == "ensemble":
            from ..ml.seed_predictor import EnsembleOptimizer
            return EnsembleOptimizer(self.config.ml)
        else:
            raise ValueError(f"Unknown ML algorithm: {algo}")

    def run(self) -> dict:
        """
        Execute the AI-guided verification loop.

        Returns summary dictionary with final metrics.
        """
        logger.info("=" * 70)
        logger.info("AIa-VO: Starting AI-Guided Verification Acceleration")
        logger.info("=" * 70)

        os.makedirs(self.config.results_dir, exist_ok=True)
        start_time = time.time()

        # Phase 1: Compile the design
        logger.info("Phase 1: Compiling design...")
        compile_ok = self.runner.compile()
        if not compile_ok:
            logger.error("Compilation failed. Aborting.")
            return {"status": "error", "message": "Compilation failed"}

        # Phase 2: Initial exploration runs
        logger.info("Phase 2: Initial exploration runs...")
        self._run_exploration_phase()

        # Phase 3: AI-guided optimization loop
        logger.info("Phase 3: AI-guided optimization loop...")
        self._run_optimization_loop()

        # Phase 4: Generate reports
        elapsed = time.time() - start_time
        logger.info(f"Phase 4: Generating reports (elapsed: {elapsed:.1f}s)...")

        summary = self._generate_final_summary(elapsed)

        # Phase 5: Comparison with baseline (if enabled)
        if self.config.comparison_mode:
            logger.info("Phase 5: Running baseline comparison...")
            baseline_summary = self._run_baseline_comparison()
            summary["baseline"] = baseline_summary
            self.report_gen.generate_comparison_report(summary, baseline_summary)

        self.report_gen.generate_final_report(summary)
        self.results_db.save_summary(summary)

        logger.info("=" * 70)
        logger.info(f"AIa-VO: Complete. Coverage: {summary['final_coverage']:.2f}%")
        logger.info(f"Total iterations: {self._iteration}, Time: {elapsed:.1f}s")
        logger.info("=" * 70)

        return summary

    def _run_exploration_phase(self):
        """Run initial exploration with diverse seeds."""
        n_explore = min(self.config.min_runs_before_ai, len(self.config.baseline_seeds))
        explore_seeds = self.config.baseline_seeds[:n_explore]

        for seed in explore_seeds:
            self._run_single_iteration(seed, phase="exploration")

    def _run_optimization_loop(self):
        """Main AI-guided optimization loop."""
        target = self.config.target_coverage

        while self._iteration < self.config.max_iterations:
            current_cov = self._cumulative_report.overall_coverage if self._cumulative_report else 0

            if current_cov >= target:
                logger.info(f"Target coverage {target}% reached at iteration {self._iteration}.")
                break

            if self._check_convergence(current_cov):
                logger.info(f"Coverage converged at {current_cov:.2f}%. Stopping.")
                break

            # Get next seed from AI/ML
            next_seed = self._get_next_seed()
            self._run_single_iteration(next_seed, phase="optimization")

    def _run_single_iteration(self, seed: int, phase: str = "optimization"):
        """Run a single simulation iteration and process results."""
        self._iteration += 1
        logger.info(f"[Iter {self._iteration}] Running simulation with seed={seed} ({phase})")

        # Run simulation
        run_result = self.runner.run_simulation(
            seed=seed,
            num_items=self.config.simulation.default_num_items,
            iteration=self._iteration,
        )

        # Parse coverage
        report = self._parse_run_results(run_result, seed)
        self._all_reports.append(report)

        # Merge with cumulative coverage
        self._cumulative_report = self.parser.merge_reports(self._all_reports)

        # Analyze gaps
        analysis = self.analyzer.analyze(self._cumulative_report)

        # Record metrics
        self.metrics.record_iteration(
            iteration=self._iteration,
            seed=seed,
            phase=phase,
            coverage=self._cumulative_report.overall_coverage,
            gap_count=analysis.total_uncovered,
            wall_time=report.wall_time_seconds,
        )

        # Update ML model with feedback
        if self._ml_optimizer:
            coverage_delta = self._compute_coverage_delta(report)
            self._ml_optimizer.update(seed, coverage_delta, analysis)

        # Consult LLM if stagnation detected
        if analysis.stagnation_detected and self._llm_client:
            self._consult_llm(analysis)

        logger.info(
            f"[Iter {self._iteration}] Cumulative coverage: "
            f"{self._cumulative_report.overall_coverage:.2f}% "
            f"({analysis.total_uncovered} uncovered bins)"
        )

        self.results_db.save_iteration(self._iteration, seed, report, analysis)

    def _parse_run_results(self, run_result: dict, seed: int) -> CoverageReport:
        """Parse simulation run results into a coverage report."""
        report = CoverageReport(seed=seed, iteration=self._iteration)

        if run_result.get("log_file"):
            log_report = self.parser.parse_vcs_log(run_result["log_file"])
            report.pass_count = log_report.pass_count
            report.fail_count = log_report.fail_count
            report.simulation_time_ns = log_report.simulation_time_ns

        if run_result.get("coverage_dir"):
            cov_report = self.parser.parse_coverage_db(run_result["coverage_dir"])
            report.coverpoints = cov_report.coverpoints
            report.crosses = cov_report.crosses

        report.wall_time_seconds = run_result.get("wall_time", 0.0)
        report.num_transactions = run_result.get("num_transactions",
                                                  self.config.simulation.default_num_items)
        report.compute_overall()
        return report

    def _get_next_seed(self) -> int:
        """Get the next seed using ML optimization or fallback strategies."""
        if self._ml_optimizer:
            try:
                seed = self._ml_optimizer.suggest_seed()
                logger.info(f"ML optimizer suggested seed: {seed}")
                return seed
            except Exception as e:
                logger.warning(f"ML seed suggestion failed: {e}")

        return self.seed_mgr.generate_smart_seed(
            used_seeds=[r.seed for r in self._all_reports],
            coverage_trend=self.analyzer.get_coverage_trend(),
        )

    def _compute_coverage_delta(self, report: CoverageReport) -> float:
        """Compute coverage improvement from this run."""
        if len(self._all_reports) < 2:
            return report.overall_coverage

        prev_merged = self.parser.merge_reports(self._all_reports[:-1])
        return self._cumulative_report.overall_coverage - prev_merged.overall_coverage

    def _check_convergence(self, current_cov: float) -> bool:
        """Check if coverage has converged."""
        trend = self.analyzer.get_coverage_trend()
        if len(trend) < 2:
            return False

        delta = abs(trend[-1] - trend[-2])
        if delta < self.config.convergence_threshold:
            self._converge_count += 1
        else:
            self._converge_count = 0

        return self._converge_count >= self.config.convergence_patience

    def _consult_llm(self, analysis: GapAnalysis):
        """Consult LLM for strategy when coverage stagnates."""
        if not self._llm_client:
            return

        try:
            prompt_data = {
                "coverage": analysis.coverage_pct,
                "uncovered_bins": [
                    {"coverpoint": g.coverpoint, "bin": g.bin_name, "hits": g.hits}
                    for g in analysis.gaps[:10]
                ],
                "trend": self.analyzer.get_coverage_trend()[-5:],
                "strategy": analysis.suggested_strategy,
            }

            suggestion = self._llm_client.get_seed_strategy(prompt_data)
            logger.info(f"LLM suggestion: {suggestion}")

            if suggestion and self._ml_optimizer:
                self._ml_optimizer.incorporate_llm_hint(suggestion)
        except Exception as e:
            logger.warning(f"LLM consultation failed: {e}")

    def _run_baseline_comparison(self) -> dict:
        """Run baseline (non-AI) simulation for comparison."""
        logger.info("Running baseline comparison with random seeds...")
        baseline_reports = []
        baseline_metrics = MetricsCollector()

        for i, seed in enumerate(self.config.baseline_seeds[:self._iteration]):
            run_result = self.runner.run_simulation(
                seed=seed,
                num_items=self.config.simulation.default_num_items,
                iteration=i + 1,
                tag="baseline",
            )
            report = self._parse_run_results(run_result, seed)
            baseline_reports.append(report)

            merged = self.parser.merge_reports(baseline_reports)
            baseline_metrics.record_iteration(
                iteration=i + 1,
                seed=seed,
                phase="baseline",
                coverage=merged.overall_coverage,
                gap_count=0,
                wall_time=report.wall_time_seconds,
            )

        if baseline_reports:
            merged = self.parser.merge_reports(baseline_reports)
            return {
                "iterations": len(baseline_reports),
                "final_coverage": merged.overall_coverage,
                "total_time": sum(r.wall_time_seconds for r in baseline_reports),
                "coverage_trend": baseline_metrics.get_coverage_trend(),
            }
        return {"iterations": 0, "final_coverage": 0.0}

    def _generate_final_summary(self, elapsed: float) -> dict:
        """Generate final summary dictionary."""
        return {
            "status": "success",
            "iterations": self._iteration,
            "final_coverage": (
                self._cumulative_report.overall_coverage if self._cumulative_report else 0.0
            ),
            "elapsed_seconds": elapsed,
            "total_transactions": sum(r.num_transactions for r in self._all_reports),
            "total_pass": sum(r.pass_count for r in self._all_reports),
            "total_fail": sum(r.fail_count for r in self._all_reports),
            "coverage_trend": self.metrics.get_coverage_trend(),
            "seeds_used": [r.seed for r in self._all_reports],
            "config": {
                "llm_provider": self.config.llm.provider if self.config.enable_llm else "disabled",
                "ml_algorithm": self.config.ml.algorithm if self.config.enable_ml else "disabled",
                "target_coverage": self.config.target_coverage,
                "max_iterations": self.config.max_iterations,
            },
        }
