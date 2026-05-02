"""
Comparison engine: AI-directed vs baseline verification runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class ComparisonMetrics:
    """Quantitative comparison between two verification runs."""
    name_a: str
    name_b: str
    coverage_a: float
    coverage_b: float
    transactions_a: int
    transactions_b: int
    iterations_a: int
    iterations_b: int
    time_a: float
    time_b: float

    @property
    def coverage_improvement(self) -> float:
        return self.coverage_a - self.coverage_b

    @property
    def transaction_reduction_pct(self) -> float:
        if self.transactions_b == 0:
            return 0.0
        return (1.0 - self.transactions_a / self.transactions_b) * 100.0

    @property
    def iteration_reduction_pct(self) -> float:
        if self.iterations_b == 0:
            return 0.0
        return (1.0 - self.iterations_a / self.iterations_b) * 100.0

    @property
    def speedup(self) -> float:
        if self.time_a == 0:
            return 0.0
        return self.time_b / self.time_a if self.time_a > 0 else 0.0

    def summary(self) -> str:
        lines = [
            "=" * 70,
            f"  Comparison: {self.name_a} vs {self.name_b}",
            "=" * 70,
            f"  Coverage          : {self.coverage_a:.1f}% vs {self.coverage_b:.1f}%"
            f"  (delta {self.coverage_improvement:+.1f}%)",
            f"  Transactions      : {self.transactions_a:,} vs {self.transactions_b:,}"
            f"  (reduction {self.transaction_reduction_pct:+.1f}%)",
            f"  Iterations        : {self.iterations_a} vs {self.iterations_b}"
            f"  (reduction {self.iteration_reduction_pct:+.1f}%)",
            f"  Wall time (s)     : {self.time_a:.2f} vs {self.time_b:.2f}"
            f"  (speedup {self.speedup:.2f}x)",
            "=" * 70,
        ]
        return "\n".join(lines)


class VerificationComparator:
    """
    Compares verification results from AI-directed and baseline runs.
    """

    def compare(
        self,
        ai_data: dict,
        baseline_data: dict,
    ) -> ComparisonMetrics:
        return ComparisonMetrics(
            name_a=ai_data.get("name", "AI"),
            name_b=baseline_data.get("name", "Baseline"),
            coverage_a=ai_data.get("final_coverage", 0.0),
            coverage_b=baseline_data.get("final_coverage", 0.0),
            transactions_a=ai_data.get("total_transactions", 0),
            transactions_b=baseline_data.get("total_transactions", 0),
            iterations_a=ai_data.get("iterations", 0),
            iterations_b=baseline_data.get("iterations", 0),
            time_a=ai_data.get("total_wall_time", 0.0),
            time_b=baseline_data.get("total_wall_time", 0.0),
        )

    def compare_all(
        self,
        results: dict[str, dict],
    ) -> list[ComparisonMetrics]:
        """Compare every AI algorithm against the baseline."""
        baseline = results.get("baseline")
        if baseline is None:
            raise ValueError("No baseline results found")

        comparisons = []
        for name, data in results.items():
            if name == "baseline":
                continue
            comparisons.append(self.compare(data, baseline))
        return comparisons

    def generate_text_report(
        self,
        results: dict[str, dict],
        output_path: Optional[str | Path] = None,
    ) -> str:
        """Generate a human-readable comparison report."""
        comparisons = self.compare_all(results)
        lines = [
            "",
            "=" * 72,
            "  AId-VO — AI-Directed Verification Optimization Report",
            "=" * 72,
            "",
        ]

        # Baseline summary
        bl = results["baseline"]
        lines += [
            "BASELINE (Random / No AI)",
            f"  Final coverage  : {bl.get('final_coverage', 0):.1f}%",
            f"  Transactions    : {bl.get('total_transactions', 0):,}",
            f"  Iterations      : {bl.get('iterations', 0)}",
            f"  Wall time       : {bl.get('total_wall_time', 0):.2f}s",
            "",
        ]

        # Per-algorithm results
        for cmp in comparisons:
            lines.append(cmp.summary())
            lines.append("")

        # Coverage trace table
        lines += ["", "COVERAGE CONVERGENCE TRACE", "-" * 50]
        max_iters = 0
        for name, data in results.items():
            trace = data.get("coverage_trace", [])
            max_iters = max(max_iters, len(trace))

        header = f"{'Iter':>5}"
        for name in results:
            header += f" | {name:>12}"
        lines.append(header)
        lines.append("-" * len(header))

        for i in range(max_iters):
            row = f"{i+1:5d}"
            for name, data in results.items():
                trace = data.get("coverage_trace", [])
                val = trace[i] if i < len(trace) else trace[-1] if trace else 0.0
                row += f" | {val:11.1f}%"
            lines.append(row)

        report = "\n".join(lines)

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(report)

        return report
