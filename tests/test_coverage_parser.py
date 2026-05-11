"""Tests for the coverage parser module."""

import os
import json
import tempfile
import pytest
from ai_agent.core.coverage_parser import (
    CoverageParser, CoverageReport, CoverageBin, Coverpoint, CrossCoverage,
)


class TestCoverageBin:
    def test_covered_bin(self):
        b = CoverageBin(name="test", hits=5, at_least=1, is_covered=True)
        assert b.coverage_pct == 100.0

    def test_uncovered_bin(self):
        b = CoverageBin(name="test", hits=0, at_least=1, is_covered=False)
        assert b.coverage_pct == 0.0


class TestCoverpoint:
    def test_compute_coverage_all_covered(self):
        cp = Coverpoint(name="A")
        cp.bins = [
            CoverageBin("b1", hits=1, is_covered=True),
            CoverageBin("b2", hits=3, is_covered=True),
        ]
        cp.compute_coverage()
        assert cp.coverage_pct == 100.0

    def test_compute_coverage_partial(self):
        cp = Coverpoint(name="A")
        cp.bins = [
            CoverageBin("b1", hits=1, is_covered=True),
            CoverageBin("b2", hits=0, is_covered=False),
        ]
        cp.compute_coverage()
        assert cp.coverage_pct == 50.0

    def test_compute_coverage_empty(self):
        cp = Coverpoint(name="empty")
        cp.compute_coverage()
        assert cp.coverage_pct == 0.0


class TestCoverageReport:
    def test_compute_overall(self):
        report = CoverageReport()
        cp = Coverpoint(name="op_code")
        cp.bins = [
            CoverageBin("add", hits=10, is_covered=True),
            CoverageBin("sub", hits=10, is_covered=True),
            CoverageBin("mul", hits=0, is_covered=False),
        ]
        report.coverpoints["op_code"] = cp
        report.compute_overall()
        assert 60.0 < report.overall_coverage < 70.0

    def test_get_uncovered_bins(self):
        report = CoverageReport()
        cp = Coverpoint(name="A")
        cp.bins = [
            CoverageBin("All_Ones", hits=10, is_covered=True),
            CoverageBin("All_Zeros", hits=0, is_covered=False),
        ]
        report.coverpoints["A"] = cp
        uncovered = report.get_uncovered_bins()
        assert len(uncovered) == 1
        assert uncovered[0][1] == "All_Zeros"

    def test_to_dict(self):
        report = CoverageReport(seed=42, iteration=1)
        result = report.to_dict()
        assert result["seed"] == 42
        assert result["iteration"] == 1
        assert "coverpoints" in result


class TestCoverageParser:
    def test_create_empty_alu_report(self):
        parser = CoverageParser()
        report = parser.create_empty_alu_report()
        assert "Reset" in report.coverpoints
        assert "A" in report.coverpoints
        assert "B" in report.coverpoints
        assert "op_code" in report.coverpoints
        assert "C_in" in report.coverpoints
        assert "corner_cases" in report.crosses
        assert len(report.crosses["corner_cases"].bins) == 12

    def test_merge_reports(self):
        parser = CoverageParser()
        r1 = parser.create_empty_alu_report()
        r2 = parser.create_empty_alu_report()

        # Mark some bins as covered in r1
        r1.coverpoints["op_code"].bins[0].is_covered = True
        r1.coverpoints["op_code"].bins[0].hits = 5

        # Mark different bins in r2
        r2.coverpoints["op_code"].bins[1].is_covered = True
        r2.coverpoints["op_code"].bins[1].hits = 3

        merged = parser.merge_reports([r1, r2])
        op_bins = merged.coverpoints["op_code"].bins
        assert op_bins[0].is_covered
        assert op_bins[1].is_covered
        assert op_bins[0].hits == 5
        assert op_bins[1].hits == 3

    def test_parse_missing_file(self):
        parser = CoverageParser()
        report = parser.parse_urg_report("/nonexistent/path")
        assert report.overall_coverage == 0.0

    def test_parse_simulation_log_seed_extraction(self):
        parser = CoverageParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("+ntb_random_seed=42\n")
            f.write("UVM_INFO: pass successfully\n")
            f.write("UVM_INFO: pass successfully\n")
            f.write("UVM_ERROR: some error\n")
            tmp_path = f.name
        try:
            report = parser.parse_vcs_log(tmp_path)
            assert report.seed == 42
            assert report.pass_count == 2
            assert report.fail_count == 1
        finally:
            os.unlink(tmp_path)
