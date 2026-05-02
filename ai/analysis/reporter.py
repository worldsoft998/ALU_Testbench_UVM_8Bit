"""
Generate structured reports and coverage visualisations (text-based).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from ai.environments.alu_sim_model import CoverageModel


class CoverageReporter:
    """Produces textual coverage status reports."""

    @staticmethod
    def bin_status_table(coverage: CoverageModel) -> str:
        lines = [
            "=" * 55,
            f"  Coverage Bin Status  ({coverage.total_covered}/{coverage.NUM_BINS} = "
            f"{coverage.coverage_percentage:.1f}%)",
            "=" * 55,
            f"  {'Bin Name':<25} {'Hits':>8}  {'Status':>8}",
            "-" * 55,
        ]
        for name, count in zip(coverage.BIN_NAMES, coverage.hit_count):
            status = "HIT" if count > 0 else "MISS"
            lines.append(f"  {name:<25} {count:>8}  {status:>8}")
        lines.append("=" * 55)
        return "\n".join(lines)

    @staticmethod
    def gap_analysis(coverage: CoverageModel) -> str:
        uncovered = coverage.uncovered_bins
        if not uncovered:
            return "All coverage bins have been hit."
        lines = [
            f"Coverage gaps ({len(uncovered)} bins uncovered):",
        ]
        for b in uncovered:
            hint = ""
            if "cross1" in b:
                op = b.split("_")[0]
                hint = f" → needs A=0xFF, B=0xFF with op={op}"
            elif "cross2" in b:
                op = b.split("_")[0]
                hint = f" → needs A=0x00, B=0x00 with op={op}"
            elif "All_Ones" in b:
                hint = " → needs operand = 0xFF"
            elif "All_Zeros" in b:
                hint = " → needs operand = 0x00"
            lines.append(f"  - {b}{hint}")
        return "\n".join(lines)

    @staticmethod
    def convergence_ascii(
        traces: dict[str, list[float]],
        width: int = 60,
        height: int = 20,
    ) -> str:
        """Render an ASCII coverage-over-iterations plot."""
        if not traces:
            return "(no data)"

        max_len = max(len(t) for t in traces.values())
        if max_len == 0:
            return "(no data)"

        canvas = [[" "] * (width + 12) for _ in range(height + 2)]

        # Y-axis labels
        for r in range(height):
            pct = 100.0 * (height - r) / height
            label = f"{pct:5.0f}% |"
            for i, ch in enumerate(label):
                canvas[r][i] = ch

        # X-axis
        x_label = "        " + "-" * (width + 1) + "> iter"
        canvas[height] = list(x_label.ljust(width + 12))

        symbols = list("*+ox#@")
        legend_lines = []

        for idx, (name, trace) in enumerate(traces.items()):
            sym = symbols[idx % len(symbols)]
            legend_lines.append(f"  {sym} = {name}")
            for i, val in enumerate(trace):
                x = int(i / max(max_len - 1, 1) * (width - 1)) + 8
                y = height - 1 - int(val / 100.0 * (height - 1))
                y = max(0, min(height - 1, y))
                if 0 <= x < len(canvas[0]):
                    canvas[y][x] = sym

        plot = "\n".join("".join(row) for row in canvas)
        legend = "\n".join(legend_lines)
        return f"{plot}\n\nLegend:\n{legend}"


class ReportGenerator:
    """Combine all reporting outputs into a single markdown report."""

    def __init__(self, output_dir: str | Path = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(
        self,
        comparison_data: dict,
        output_file: str = "report.md",
    ) -> str:
        lines = [
            "# AId-VO — AI-Directed Verification Optimization Report",
            "",
            "## Summary",
            "",
        ]

        baseline = comparison_data.get("baseline", {})
        lines += [
            "### Baseline (No AI)",
            f"- **Final Coverage**: {baseline.get('final_coverage', 0):.1f}%",
            f"- **Total Transactions**: {baseline.get('total_transactions', 0):,}",
            f"- **Iterations**: {baseline.get('iterations', 0)}",
            f"- **Wall Time**: {baseline.get('total_wall_time', 0):.2f}s",
            "",
        ]

        for name, data in comparison_data.items():
            if name == "baseline":
                continue
            lines += [
                f"### {name.upper()} (AI-Directed)",
                f"- **Final Coverage**: {data.get('final_coverage', 0):.1f}%",
                f"- **Total Transactions**: {data.get('total_transactions', 0):,}",
                f"- **Iterations**: {data.get('iterations', 0)}",
                f"- **Wall Time**: {data.get('total_wall_time', 0):.2f}s",
                "",
            ]

            bl_txn = baseline.get("total_transactions", 1)
            ai_txn = data.get("total_transactions", 0)
            if bl_txn > 0:
                reduction = (1 - ai_txn / bl_txn) * 100
                lines.append(
                    f"- **Transaction Reduction vs Baseline**: {reduction:+.1f}%"
                )
            lines.append("")

        # Coverage traces
        lines += ["## Coverage Convergence", "", "```"]
        traces = {
            name: data.get("coverage_trace", [])
            for name, data in comparison_data.items()
        }
        reporter = CoverageReporter()
        lines.append(reporter.convergence_ascii(traces))
        lines += ["```", ""]

        report_text = "\n".join(lines)
        out_path = self.output_dir / output_file
        out_path.write_text(report_text)
        return report_text
