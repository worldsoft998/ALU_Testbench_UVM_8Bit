"""
Metrics collection and comparison between AI-guided and baseline runs.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IterationMetric:
    """Metrics for a single iteration."""
    iteration: int
    seed: int
    phase: str
    coverage: float
    gap_count: int
    wall_time: float
    cumulative_time: float = 0.0


class MetricsCollector:
    """Collects and computes comparison metrics."""

    def __init__(self):
        self._metrics: list = []
        self._cumulative_time = 0.0

    def record_iteration(self, iteration: int, seed: int, phase: str,
                         coverage: float, gap_count: int, wall_time: float):
        """Record metrics for one iteration."""
        self._cumulative_time += wall_time
        m = IterationMetric(
            iteration=iteration,
            seed=seed,
            phase=phase,
            coverage=coverage,
            gap_count=gap_count,
            wall_time=wall_time,
            cumulative_time=self._cumulative_time,
        )
        self._metrics.append(m)

    def get_coverage_trend(self) -> list:
        """Return coverage at each iteration."""
        return [m.coverage for m in self._metrics]

    def get_time_trend(self) -> list:
        """Return cumulative time at each iteration."""
        return [m.cumulative_time for m in self._metrics]

    def get_gap_trend(self) -> list:
        """Return gap count at each iteration."""
        return [m.gap_count for m in self._metrics]

    def iterations_to_target(self, target: float) -> int:
        """Return number of iterations to reach target coverage, or -1."""
        for m in self._metrics:
            if m.coverage >= target:
                return m.iteration
        return -1

    def time_to_target(self, target: float) -> float:
        """Return wall time to reach target coverage, or -1."""
        for m in self._metrics:
            if m.coverage >= target:
                return m.cumulative_time
        return -1.0

    def compute_comparison(self, baseline_metrics: "MetricsCollector") -> dict:
        """Compare AI-guided metrics vs baseline."""
        ai_trend = self.get_coverage_trend()
        bl_trend = baseline_metrics.get_coverage_trend()

        comparison = {
            "ai_final_coverage": ai_trend[-1] if ai_trend else 0,
            "baseline_final_coverage": bl_trend[-1] if bl_trend else 0,
            "ai_iterations": len(ai_trend),
            "baseline_iterations": len(bl_trend),
            "ai_total_time": self._cumulative_time,
            "baseline_total_time": baseline_metrics._cumulative_time,
        }

        # Coverage improvement
        if bl_trend:
            comparison["coverage_improvement"] = (
                comparison["ai_final_coverage"] - comparison["baseline_final_coverage"]
            )

        # Speedup at various coverage targets
        for target in [50.0, 75.0, 90.0, 95.0, 100.0]:
            ai_iters = self.iterations_to_target(target)
            bl_iters = baseline_metrics.iterations_to_target(target)
            key = f"speedup_at_{int(target)}pct"
            if ai_iters > 0 and bl_iters > 0:
                comparison[key] = round(bl_iters / ai_iters, 2)
            elif ai_iters > 0 and bl_iters < 0:
                comparison[key] = "AI_only"
            else:
                comparison[key] = "N/A"

        # Area under coverage curve (higher is better)
        comparison["ai_auc"] = sum(ai_trend) / max(len(ai_trend), 1)
        comparison["baseline_auc"] = sum(bl_trend) / max(len(bl_trend), 1)

        return comparison

    def to_dict(self) -> dict:
        return {
            "iterations": [
                {
                    "iter": m.iteration,
                    "seed": m.seed,
                    "phase": m.phase,
                    "coverage": round(m.coverage, 4),
                    "gaps": m.gap_count,
                    "time": round(m.wall_time, 2),
                    "cum_time": round(m.cumulative_time, 2),
                }
                for m in self._metrics
            ],
            "total_time": round(self._cumulative_time, 2),
            "final_coverage": self._metrics[-1].coverage if self._metrics else 0,
        }
