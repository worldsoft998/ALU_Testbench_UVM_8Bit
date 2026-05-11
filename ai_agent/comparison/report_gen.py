"""
Report generation for AI-guided verification results.
Produces text, JSON, and markdown reports.
"""

import os
import json
import logging
from datetime import datetime
from ..core.config import AgentConfig

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate comprehensive verification reports."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.results_dir = os.path.join(config.project_root, config.results_dir)

    def generate_final_report(self, summary: dict):
        """Generate the final AI-guided verification report."""
        os.makedirs(self.results_dir, exist_ok=True)

        # JSON report
        json_path = os.path.join(self.results_dir, "ai_guided_report.json")
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Markdown report
        md_path = os.path.join(self.results_dir, "ai_guided_report.md")
        md_content = self._format_markdown_report(summary)
        with open(md_path, "w") as f:
            f.write(md_content)

        # Text summary
        txt_path = os.path.join(self.results_dir, "ai_guided_report.txt")
        txt_content = self._format_text_report(summary)
        with open(txt_path, "w") as f:
            f.write(txt_content)

        logger.info(f"Reports generated in: {self.results_dir}")

    def generate_comparison_report(self, ai_summary: dict, baseline_summary: dict):
        """Generate comparison report between AI and baseline."""
        os.makedirs(self.results_dir, exist_ok=True)

        report = {
            "generated_at": datetime.now().isoformat(),
            "ai_guided": {
                "iterations": ai_summary.get("iterations", 0),
                "final_coverage": ai_summary.get("final_coverage", 0),
                "elapsed_seconds": ai_summary.get("elapsed_seconds", 0),
                "seeds_used": ai_summary.get("seeds_used", []),
            },
            "baseline": {
                "iterations": baseline_summary.get("iterations", 0),
                "final_coverage": baseline_summary.get("final_coverage", 0),
                "total_time": baseline_summary.get("total_time", 0),
            },
        }

        # Compute improvements
        ai_cov = report["ai_guided"]["final_coverage"]
        bl_cov = report["baseline"]["final_coverage"]
        ai_iter = report["ai_guided"]["iterations"]
        bl_iter = report["baseline"]["iterations"]

        report["comparison"] = {
            "coverage_difference": round(ai_cov - bl_cov, 4),
            "iteration_ratio": round(bl_iter / max(ai_iter, 1), 2),
            "ai_advantage": ai_cov > bl_cov,
        }

        # Coverage trend comparison
        ai_trend = ai_summary.get("coverage_trend", [])
        bl_trend = baseline_summary.get("coverage_trend", [])
        report["coverage_trends"] = {
            "ai_guided": [round(x, 2) for x in ai_trend],
            "baseline": [round(x, 2) for x in bl_trend],
        }

        json_path = os.path.join(self.results_dir, "comparison_report.json")
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)

        md_path = os.path.join(self.results_dir, "comparison_report.md")
        md_content = self._format_comparison_markdown(report)
        with open(md_path, "w") as f:
            f.write(md_content)

        logger.info(f"Comparison report saved: {json_path}")

    def _format_markdown_report(self, summary: dict) -> str:
        """Format summary as markdown."""
        lines = [
            "# AIa-VO Verification Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Status | {summary.get('status', 'N/A')} |",
            f"| Final Coverage | {summary.get('final_coverage', 0):.2f}% |",
            f"| Total Iterations | {summary.get('iterations', 0)} |",
            f"| Elapsed Time | {summary.get('elapsed_seconds', 0):.1f}s |",
            f"| Total Transactions | {summary.get('total_transactions', 0):,} |",
            f"| Pass Count | {summary.get('total_pass', 0):,} |",
            f"| Fail Count | {summary.get('total_fail', 0)} |",
            "",
            "## Configuration",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
        ]

        config = summary.get("config", {})
        for k, v in config.items():
            lines.append(f"| {k} | {v} |")

        lines.extend([
            "",
            "## Coverage Trend",
            "",
            "```",
        ])

        trend = summary.get("coverage_trend", [])
        for i, cov in enumerate(trend):
            bar = "#" * int(cov / 2)
            lines.append(f"Iter {i+1:3d}: {cov:6.2f}% |{bar}")

        lines.extend([
            "```",
            "",
            "## Seeds Used",
            "",
            f"```",
            str(summary.get("seeds_used", [])),
            "```",
        ])

        return "\n".join(lines)

    def _format_text_report(self, summary: dict) -> str:
        """Format summary as plain text."""
        lines = [
            "=" * 70,
            "AIa-VO: AI-Guided Verification Acceleration Report",
            "=" * 70,
            "",
            f"Status:           {summary.get('status', 'N/A')}",
            f"Final Coverage:   {summary.get('final_coverage', 0):.2f}%",
            f"Iterations:       {summary.get('iterations', 0)}",
            f"Elapsed Time:     {summary.get('elapsed_seconds', 0):.1f}s",
            f"Transactions:     {summary.get('total_transactions', 0):,}",
            f"Pass/Fail:        {summary.get('total_pass', 0)}/{summary.get('total_fail', 0)}",
            "",
            "-" * 70,
            "Coverage Trend:",
            "-" * 70,
        ]

        trend = summary.get("coverage_trend", [])
        for i, cov in enumerate(trend):
            bar = "█" * int(cov / 2.5) + "░" * (40 - int(cov / 2.5))
            lines.append(f"  Iter {i+1:3d}: [{bar}] {cov:6.2f}%")

        lines.extend(["", "=" * 70])
        return "\n".join(lines)

    def _format_comparison_markdown(self, report: dict) -> str:
        """Format comparison report as markdown."""
        ai = report.get("ai_guided", {})
        bl = report.get("baseline", {})
        comp = report.get("comparison", {})

        lines = [
            "# AIa-VO: AI vs Baseline Comparison Report",
            "",
            f"**Generated:** {report.get('generated_at', '')}",
            "",
            "## Results Summary",
            "",
            "| Metric | AI-Guided | Baseline | Difference |",
            "|--------|-----------|----------|------------|",
            f"| Final Coverage | {ai.get('final_coverage', 0):.2f}% "
            f"| {bl.get('final_coverage', 0):.2f}% "
            f"| {comp.get('coverage_difference', 0):+.2f}% |",
            f"| Iterations | {ai.get('iterations', 0)} "
            f"| {bl.get('iterations', 0)} "
            f"| {comp.get('iteration_ratio', 0):.2f}x |",
            f"| Time (s) | {ai.get('elapsed_seconds', 0):.1f} "
            f"| {bl.get('total_time', 0):.1f} | - |",
            "",
            "## Coverage Trends",
            "",
            "### AI-Guided",
            "```",
        ]

        trends = report.get("coverage_trends", {})
        for i, cov in enumerate(trends.get("ai_guided", [])):
            bar = "#" * int(cov / 2.5)
            lines.append(f"  Iter {i+1:3d}: {cov:6.2f}% |{bar}")

        lines.extend([
            "```",
            "",
            "### Baseline (Random Seeds)",
            "```",
        ])

        for i, cov in enumerate(trends.get("baseline", [])):
            bar = "#" * int(cov / 2.5)
            lines.append(f"  Iter {i+1:3d}: {cov:6.2f}% |{bar}")

        lines.extend([
            "```",
            "",
            "## Conclusion",
            "",
        ])

        if comp.get("ai_advantage"):
            lines.append(
                f"The AI-guided approach achieved **{comp.get('coverage_difference', 0):+.2f}%** "
                f"higher coverage with a **{comp.get('iteration_ratio', 0):.1f}x** "
                "iteration efficiency ratio."
            )
        else:
            lines.append(
                "The baseline approach matched or exceeded AI-guided coverage in this run. "
                "This may indicate the coverage space is easily reachable with random seeds."
            )

        return "\n".join(lines)
