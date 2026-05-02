"""
Unified coverage parser that abstracts over VCS coverage reports and the
Python coverage model, providing a common interface to the AI agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from ai.environments.alu_sim_model import CoverageModel
from ai.parsers.vcs_log_parser import VCSLogParser, VCSCoverageReportParser


class CoverageSnapshot:
    """Immutable snapshot of coverage state at a point in time."""

    __slots__ = (
        "iteration", "total_transactions", "coverage_pct",
        "covered_bins", "total_bins", "bin_vector", "bin_names",
        "uncovered_bins", "source",
    )

    def __init__(
        self,
        iteration: int,
        total_transactions: int,
        coverage_pct: float,
        covered_bins: int,
        total_bins: int,
        bin_vector: np.ndarray,
        bin_names: list[str],
        uncovered_bins: list[str],
        source: str = "python",
    ):
        self.iteration = iteration
        self.total_transactions = total_transactions
        self.coverage_pct = coverage_pct
        self.covered_bins = covered_bins
        self.total_bins = total_bins
        self.bin_vector = bin_vector
        self.bin_names = bin_names
        self.uncovered_bins = uncovered_bins
        self.source = source

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "total_transactions": self.total_transactions,
            "coverage_pct": self.coverage_pct,
            "covered_bins": self.covered_bins,
            "total_bins": self.total_bins,
            "uncovered_bins": self.uncovered_bins,
            "source": self.source,
        }


class UnifiedCoverageParser:
    """
    Creates ``CoverageSnapshot`` objects from either a Python ``CoverageModel``
    or from VCS simulation artifacts.
    """

    def __init__(self) -> None:
        self._log_parser = VCSLogParser()
        self._report_parser = VCSCoverageReportParser()

    def from_python_model(
        self,
        model: CoverageModel,
        iteration: int = 0,
        total_transactions: int = 0,
    ) -> CoverageSnapshot:
        return CoverageSnapshot(
            iteration=iteration,
            total_transactions=total_transactions,
            coverage_pct=model.coverage_percentage,
            covered_bins=model.total_covered,
            total_bins=CoverageModel.NUM_BINS,
            bin_vector=model.covered_vector.copy(),
            bin_names=list(CoverageModel.BIN_NAMES),
            uncovered_bins=model.uncovered_bins,
            source="python",
        )

    def from_vcs_log(
        self,
        log_path: str | Path,
        iteration: int = 0,
    ) -> CoverageSnapshot:
        result = self._log_parser.parse_file(log_path)
        cov_model = CoverageModel()
        for txn in result.transactions:
            cov_model.sample(txn)

        return CoverageSnapshot(
            iteration=iteration,
            total_transactions=result.num_transactions,
            coverage_pct=max(result.coverage_pct, cov_model.coverage_percentage),
            covered_bins=cov_model.total_covered,
            total_bins=CoverageModel.NUM_BINS,
            bin_vector=cov_model.covered_vector.copy(),
            bin_names=list(CoverageModel.BIN_NAMES),
            uncovered_bins=cov_model.uncovered_bins,
            source="vcs",
        )

    def from_vcs_coverage_report(
        self,
        report_path: str | Path,
        iteration: int = 0,
        total_transactions: int = 0,
    ) -> CoverageSnapshot:
        data = self._report_parser.parse_file(report_path)
        bin_names = list(CoverageModel.BIN_NAMES)
        bin_vector = np.zeros(CoverageModel.NUM_BINS, dtype=np.float32)
        for i, name in enumerate(bin_names):
            short = name.split("_", 1)[-1] if "_" in name else name
            if short in data.get("bins", {}):
                bin_vector[i] = 1.0 if data["bins"][short] > 0 else 0.0

        covered = int(np.sum(bin_vector > 0))
        return CoverageSnapshot(
            iteration=iteration,
            total_transactions=total_transactions,
            coverage_pct=data.get("overall_coverage", 0.0),
            covered_bins=covered,
            total_bins=CoverageModel.NUM_BINS,
            bin_vector=bin_vector,
            bin_names=bin_names,
            uncovered_bins=[n for n, v in zip(bin_names, bin_vector) if v == 0],
            source="vcs_report",
        )
