"""
Results storage for tracking simulation history and metrics.
"""

import os
import json
import csv
import logging
from datetime import datetime
from typing import Optional
from ..core.config import AgentConfig
from ..core.coverage_parser import CoverageReport
from ..core.gap_analyzer import GapAnalysis

logger = logging.getLogger(__name__)


class ResultsDB:
    """Lightweight results database using JSON and CSV files."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.results_dir = os.path.join(config.project_root, config.results_dir)
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(self.results_dir, self._session_id)
        os.makedirs(self._session_dir, exist_ok=True)
        self._csv_path = os.path.join(self._session_dir, "iterations.csv")
        self._init_csv()

    def _init_csv(self):
        """Initialize CSV file with headers."""
        with open(self._csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "iteration", "seed", "phase",
                "coverage_pct", "uncovered_bins", "pass_count", "fail_count",
                "wall_time_s", "num_transactions", "coverage_delta",
            ])

    def save_iteration(self, iteration: int, seed: int,
                       report: CoverageReport, analysis: GapAnalysis):
        """Save a single iteration's results."""
        # Append to CSV
        with open(self._csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                iteration, seed, "ai",
                round(report.overall_coverage, 4),
                analysis.total_uncovered,
                report.pass_count, report.fail_count,
                round(report.wall_time_seconds, 2),
                report.num_transactions,
                round(analysis.coverage_pct, 4),
            ])

        # Save detailed JSON
        iter_path = os.path.join(
            self._session_dir, f"iter_{iteration:04d}.json"
        )
        data = {
            "iteration": iteration,
            "seed": seed,
            "timestamp": datetime.now().isoformat(),
            "coverage_report": report.to_dict(),
            "gap_analysis": {
                "total_uncovered": analysis.total_uncovered,
                "total_bins": analysis.total_bins,
                "coverage_pct": analysis.coverage_pct,
                "stagnation": analysis.stagnation_detected,
                "strategy": analysis.suggested_strategy,
                "gaps": [
                    {
                        "coverpoint": g.coverpoint,
                        "bin": g.bin_name,
                        "hits": g.hits,
                        "priority": g.priority,
                        "description": g.description,
                    }
                    for g in analysis.gaps
                ],
            },
        }
        with open(iter_path, "w") as f:
            json.dump(data, f, indent=2)

    def save_summary(self, summary: dict):
        """Save final session summary."""
        summary_path = os.path.join(self._session_dir, "summary.json")
        summary["session_id"] = self._session_id
        summary["timestamp"] = datetime.now().isoformat()
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Summary saved: {summary_path}")

    def load_session(self, session_id: str) -> Optional[dict]:
        """Load a previous session's summary."""
        summary_path = os.path.join(
            self.results_dir, session_id, "summary.json"
        )
        if os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                return json.load(f)
        return None

    def list_sessions(self) -> list:
        """List all stored sessions."""
        sessions = []
        if not os.path.exists(self.results_dir):
            return sessions
        for d in sorted(os.listdir(self.results_dir)):
            summary_path = os.path.join(self.results_dir, d, "summary.json")
            if os.path.exists(summary_path):
                with open(summary_path, "r") as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": d,
                    "coverage": data.get("final_coverage", 0),
                    "iterations": data.get("iterations", 0),
                })
        return sessions

    def get_session_dir(self) -> str:
        return self._session_dir
