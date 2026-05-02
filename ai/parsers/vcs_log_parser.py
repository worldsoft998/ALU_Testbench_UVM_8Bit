"""
Parse Synopsys VCS simulation logs to extract transaction data and coverage
information.  Works with the unmodified ALU UVM testbench output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ai.environments.alu_sim_model import ALUTransaction


@dataclass
class SimulationResult:
    """Aggregated results from one VCS simulation run."""
    seed: int = 0
    num_transactions: int = 0
    errors: int = 0
    passes: int = 0
    coverage_pct: float = 0.0
    transactions: list[ALUTransaction] = field(default_factory=list)
    raw_log: str = ""
    wall_time_s: float = 0.0
    uvm_errors: int = 0
    uvm_warnings: int = 0


class VCSLogParser:
    """
    Extracts structured data from VCS + UVM simulation log files.

    The parser is designed to work with the *unmodified* ALU testbench and
    standard UVM reporting.  It reads:
        - UVM report summary  (pass / error counts)
        - Scoreboard transaction data
        - Coverage percentages from ``$get_coverage`` / ``-cm_log``
        - Simulation wall time
    """

    # Regex patterns for standard UVM / VCS output
    _RE_UVM_SUMMARY = re.compile(
        r"UVM_(?:INFO|WARNING|ERROR|FATAL)\s*:\s*(\d+)", re.IGNORECASE
    )
    _RE_SCB_ERROR = re.compile(
        r"error.*A=\s*(\d+).*B=\s*(\d+).*opcode\s*=\s*(\S+).*Result\s+(\d+).*expected\s+(\d+)",
        re.IGNORECASE,
    )
    _RE_COVERAGE = re.compile(
        r"(?:Total|Overall)\s+(?:functional\s+)?coverage[:\s]+(\d+\.?\d*)%?",
        re.IGNORECASE,
    )
    _RE_SIM_TIME = re.compile(
        r"(?:CPU|wall)\s+time[:\s]+(\d+\.?\d*)\s*s", re.IGNORECASE
    )
    _RE_SEED = re.compile(
        r"\+ntb_random_seed\s*=\s*(\d+)", re.IGNORECASE
    )
    _RE_TXN_LINE = re.compile(
        r"A=\s*(\d+).*B=\s*(\d+).*opcode\s*=\s*([01]+).*Result\s+(\d+)",
        re.IGNORECASE,
    )

    def parse_file(self, log_path: str | Path) -> SimulationResult:
        path = Path(log_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {path}")
        text = path.read_text(errors="replace")
        return self.parse_text(text)

    def parse_text(self, text: str) -> SimulationResult:
        result = SimulationResult(raw_log=text)

        # Seed
        m = self._RE_SEED.search(text)
        if m:
            result.seed = int(m.group(1))

        # UVM report counts: INFO(0), WARNING(1), ERROR(2), FATAL(3)
        uvm_counts = self._RE_UVM_SUMMARY.findall(text)
        if len(uvm_counts) >= 3:
            result.uvm_warnings = int(uvm_counts[1])
            result.uvm_errors = int(uvm_counts[2])
        elif len(uvm_counts) >= 2:
            result.uvm_warnings = int(uvm_counts[1])
            result.uvm_errors = 0

        # Error lines from scoreboard
        errors = self._RE_SCB_ERROR.findall(text)
        result.errors = len(errors)

        # Coverage
        cov_matches = self._RE_COVERAGE.findall(text)
        if cov_matches:
            result.coverage_pct = float(cov_matches[-1])

        # Simulation time
        tm = self._RE_SIM_TIME.search(text)
        if tm:
            result.wall_time_s = float(tm.group(1))

        # Transaction extraction
        txn_lines = self._RE_TXN_LINE.findall(text)
        for a_s, b_s, op_s, res_s in txn_lines:
            txn = ALUTransaction(
                a=int(a_s), b=int(b_s),
                opcode=int(op_s, 2) if all(c in "01" for c in op_s) else int(op_s),
                result=int(res_s),
            )
            result.transactions.append(txn)

        result.num_transactions = max(len(result.transactions), result.num_transactions)

        # Count passes (lines containing "pass successfully")
        result.passes = text.lower().count("pass successfully")

        return result


class VCSCoverageReportParser:
    """
    Parse the text/URG coverage report produced by VCS ``-cm`` / ``urg``.

    Handles both the text summary and the detailed per-group breakdown.
    """

    _RE_GROUP = re.compile(
        r"(?:Covergroup|GROUP)\s*:\s*(\S+).*?(\d+\.?\d*)%",
        re.IGNORECASE,
    )
    _RE_BIN = re.compile(
        r"(?:bin|cross)\s+(\w+)\s+.*?(\d+)\s+hit",
        re.IGNORECASE,
    )

    def parse_file(self, report_path: str | Path) -> dict:
        text = Path(report_path).read_text(errors="replace")
        return self.parse_text(text)

    def parse_text(self, text: str) -> dict:
        groups: dict[str, float] = {}
        for m in self._RE_GROUP.finditer(text):
            groups[m.group(1)] = float(m.group(2))

        bins: dict[str, int] = {}
        for m in self._RE_BIN.finditer(text):
            bins[m.group(1)] = int(m.group(2))

        overall = max(groups.values()) if groups else 0.0
        return {
            "overall_coverage": overall,
            "groups": groups,
            "bins": bins,
        }
