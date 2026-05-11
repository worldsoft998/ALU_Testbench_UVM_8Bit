"""
Parse VCS/URG coverage reports to extract functional coverage data.
Supports both text-based URG reports and VCS coverage database formats.
"""

import re
import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CoverageBin:
    """A single coverage bin."""
    name: str
    hits: int = 0
    at_least: int = 1
    is_covered: bool = False

    @property
    def coverage_pct(self) -> float:
        return 100.0 if self.hits >= self.at_least else 0.0


@dataclass
class Coverpoint:
    """A coverpoint with its bins."""
    name: str
    bins: list = field(default_factory=list)
    coverage_pct: float = 0.0

    def compute_coverage(self):
        if not self.bins:
            return
        covered = sum(1 for b in self.bins if b.is_covered)
        self.coverage_pct = (covered / len(self.bins)) * 100.0


@dataclass
class CrossCoverage:
    """Cross coverage with its bins."""
    name: str
    bins: list = field(default_factory=list)
    coverage_pct: float = 0.0

    def compute_coverage(self):
        if not self.bins:
            return
        covered = sum(1 for b in self.bins if b.is_covered)
        self.coverage_pct = (covered / len(self.bins)) * 100.0


@dataclass
class CoverageReport:
    """Complete coverage report from a simulation run."""
    seed: int = 0
    iteration: int = 0
    num_transactions: int = 0
    coverpoints: dict = field(default_factory=dict)
    crosses: dict = field(default_factory=dict)
    overall_coverage: float = 0.0
    simulation_time_ns: int = 0
    wall_time_seconds: float = 0.0
    pass_count: int = 0
    fail_count: int = 0

    def compute_overall(self):
        """Compute weighted overall coverage."""
        all_items = []
        for cp in self.coverpoints.values():
            cp.compute_coverage()
            all_items.append(cp.coverage_pct)
        for cr in self.crosses.values():
            cr.compute_coverage()
            all_items.append(cr.coverage_pct)
        if all_items:
            self.overall_coverage = sum(all_items) / len(all_items)

    def get_uncovered_bins(self) -> list:
        """Return list of all uncovered bins with their parent names."""
        uncovered = []
        for cp_name, cp in self.coverpoints.items():
            for b in cp.bins:
                if not b.is_covered:
                    uncovered.append((cp_name, b.name, b.hits))
        for cr_name, cr in self.crosses.items():
            for b in cr.bins:
                if not b.is_covered:
                    uncovered.append((cr_name, b.name, b.hits))
        return uncovered

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "seed": self.seed,
            "iteration": self.iteration,
            "num_transactions": self.num_transactions,
            "overall_coverage": self.overall_coverage,
            "simulation_time_ns": self.simulation_time_ns,
            "wall_time_seconds": self.wall_time_seconds,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "coverpoints": {
                name: {
                    "coverage_pct": cp.coverage_pct,
                    "bins": [
                        {"name": b.name, "hits": b.hits, "covered": b.is_covered}
                        for b in cp.bins
                    ],
                }
                for name, cp in self.coverpoints.items()
            },
            "crosses": {
                name: {
                    "coverage_pct": cr.coverage_pct,
                    "bins": [
                        {"name": b.name, "hits": b.hits, "covered": b.is_covered}
                        for b in cr.bins
                    ],
                }
                for name, cr in self.crosses.items()
            },
        }


class CoverageParser:
    """Parse VCS/URG functional coverage reports."""

    # ALU-specific coverage structure based on ALU_Coverage_Collector.sv
    ALU_COVERPOINTS = {
        "Reset": ["0", "1"],
        "A": ["All_Ones", "All_Zeros", "random_stimulus"],
        "B": ["All_Ones", "All_Zeros", "random_stimulus"],
        "op_code": ["add", "sub", "mul", "div", "anding", "xoring"],
        "C_in": ["0", "1"],
    }
    ALU_CROSS_BINS = {
        "corner_cases": [
            "Add_cross1", "Add_cross2",
            "Sub_cross1", "Sub_cross2",
            "Mul_cross1", "Mul_cross2",
            "Div_cross1", "Div_cross2",
            "And_cross1", "And_cross2",
            "Xor_cross1", "Xor_cross2",
        ]
    }

    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def parse_urg_report(self, report_path: str) -> CoverageReport:
        """Parse a URG text report file."""
        report = CoverageReport()
        if not os.path.exists(report_path):
            logger.warning(f"Report file not found: {report_path}")
            return report

        with open(report_path, "r") as f:
            content = f.read()

        report = self._parse_text_report(content, report)
        report.compute_overall()
        return report

    def parse_vcs_log(self, log_path: str) -> CoverageReport:
        """Parse VCS simulation log to extract coverage and test results."""
        report = CoverageReport()
        if not os.path.exists(log_path):
            logger.warning(f"Log file not found: {log_path}")
            return report

        with open(log_path, "r") as f:
            content = f.read()

        report = self._parse_simulation_log(content, report)
        report.compute_overall()
        return report

    def parse_coverage_db(self, db_path: str) -> CoverageReport:
        """Parse VCS coverage database directory."""
        report = CoverageReport()
        if not os.path.isdir(db_path):
            logger.warning(f"Coverage DB not found: {db_path}")
            return report

        # Look for URG-generated reports
        for root, dirs, files in os.walk(db_path):
            for f in files:
                if f.endswith(".txt") and "grp" in f.lower():
                    txt_report = os.path.join(root, f)
                    report = self.parse_urg_report(txt_report)
                    break

        report.compute_overall()
        return report

    def _parse_text_report(self, content: str, report: CoverageReport) -> CoverageReport:
        """Parse URG text-format coverage report."""
        # Parse covergroup summary
        cg_pattern = r"Covergroup\s+Coverage\s*\n[-=]+\s*\n(.*?)(?:\n\n|\Z)"
        cg_match = re.search(cg_pattern, content, re.DOTALL)

        # Parse individual coverpoint details
        cp_pattern = r"Coverpoint\s+:\s+(\w+)\s*\n.*?Coverage\s*:\s*([\d.]+)%"
        for match in re.finditer(cp_pattern, content, re.DOTALL):
            cp_name = match.group(1)
            cp_cov = float(match.group(2))
            cp = Coverpoint(name=cp_name, coverage_pct=cp_cov)
            report.coverpoints[cp_name] = cp

        # Parse bin details
        bin_pattern = r"bin\s+(\w+)\s+(\d+)\s+(\d+)\s+(Covered|Uncovered)"
        for match in re.finditer(bin_pattern, content):
            bin_name = match.group(1)
            hits = int(match.group(2))
            at_least = int(match.group(3))
            covered = match.group(4) == "Covered"
            cb = CoverageBin(name=bin_name, hits=hits, at_least=at_least, is_covered=covered)
            # Assign to appropriate coverpoint
            for cp_name, cp in report.coverpoints.items():
                if bin_name in self.ALU_COVERPOINTS.get(cp_name, []):
                    cp.bins.append(cb)

        # Parse cross coverage
        cross_pattern = r"Cross\s+:\s+(\w+)\s*\n.*?Coverage\s*:\s*([\d.]+)%"
        for match in re.finditer(cross_pattern, content, re.DOTALL):
            cr_name = match.group(1)
            cr_cov = float(match.group(2))
            cr = CrossCoverage(name=cr_name, coverage_pct=cr_cov)
            report.crosses[cr_name] = cr

        # Parse overall coverage
        overall_pattern = r"(?:Total|Overall)\s+Coverage\s*:\s*([\d.]+)%"
        match = re.search(overall_pattern, content)
        if match:
            report.overall_coverage = float(match.group(1))

        return report

    def _parse_simulation_log(self, content: str, report: CoverageReport) -> CoverageReport:
        """Parse VCS simulation log for coverage info and pass/fail counts."""
        # Extract seed
        seed_pattern = r"\+ntb_random_seed\s*=\s*(\d+)"
        match = re.search(seed_pattern, content)
        if match:
            report.seed = int(match.group(1))

        # Count UVM errors vs passes
        error_count = len(re.findall(r"UVM_ERROR[\s:]", content))
        pass_count = len(re.findall(r"pass successfully", content))
        report.fail_count = error_count
        report.pass_count = pass_count

        # Extract coverage summary from UVM report
        cov_pattern = r"Coverage\s*=\s*([\d.]+)"
        matches = re.findall(cov_pattern, content)
        if matches:
            report.overall_coverage = float(matches[-1])

        # Parse detailed covergroup report in the UVM output
        self._parse_uvm_coverage_output(content, report)

        # Extract simulation time
        time_pattern = r"\$finish.*?:\s*(\d+)\s*(?:ns|ps)"
        match = re.search(time_pattern, content)
        if match:
            report.simulation_time_ns = int(match.group(1))

        return report

    def _parse_uvm_coverage_output(self, content: str, report: CoverageReport):
        """Parse the coverage portion of UVM simulation output."""
        # Look for covergroup report sections
        # VCS outputs coverage in a structured format after simulation

        # Parse coverpoint percentages from report
        cp_pct_pattern = r"(\w+)\s+(\d+(?:\.\d+)?)\s*%\s+(?:Covered|Uncovered)"
        for match in re.finditer(cp_pct_pattern, content):
            name = match.group(1)
            pct = float(match.group(2))
            if name in self.ALU_COVERPOINTS:
                cp = report.coverpoints.get(name, Coverpoint(name=name))
                cp.coverage_pct = pct
                report.coverpoints[name] = cp

    def create_empty_alu_report(self) -> CoverageReport:
        """Create an empty ALU coverage report with proper structure."""
        report = CoverageReport()
        for cp_name, bins in self.ALU_COVERPOINTS.items():
            cp = Coverpoint(name=cp_name)
            for bin_name in bins:
                cp.bins.append(CoverageBin(name=bin_name))
            report.coverpoints[cp_name] = cp
        for cr_name, bins in self.ALU_CROSS_BINS.items():
            cr = CrossCoverage(name=cr_name)
            for bin_name in bins:
                cr.bins.append(CoverageBin(name=bin_name))
            report.crosses[cr_name] = cr
        return report

    def merge_reports(self, reports: list) -> CoverageReport:
        """Merge multiple coverage reports into one cumulative report."""
        merged = self.create_empty_alu_report()
        merged.num_transactions = sum(r.num_transactions for r in reports)
        merged.wall_time_seconds = sum(r.wall_time_seconds for r in reports)
        merged.pass_count = sum(r.pass_count for r in reports)
        merged.fail_count = sum(r.fail_count for r in reports)

        for r in reports:
            for cp_name, cp in r.coverpoints.items():
                if cp_name in merged.coverpoints:
                    mcp = merged.coverpoints[cp_name]
                    for rb in cp.bins:
                        for mb in mcp.bins:
                            if mb.name == rb.name:
                                mb.hits += rb.hits
                                if rb.is_covered:
                                    mb.is_covered = True
                                break
            for cr_name, cr in r.crosses.items():
                if cr_name in merged.crosses:
                    mcr = merged.crosses[cr_name]
                    for rb in cr.bins:
                        for mb in mcr.bins:
                            if mb.name == rb.name:
                                mb.hits += rb.hits
                                if rb.is_covered:
                                    mb.is_covered = True
                                break

        merged.compute_overall()
        return merged
