"""Tests for the gap analyzer module."""

import pytest
from ai_agent.core.coverage_parser import (
    CoverageReport, CoverageBin, Coverpoint, CrossCoverage,
)
from ai_agent.core.gap_analyzer import GapAnalyzer, GapAnalysis


class TestGapAnalyzer:
    def setup_method(self):
        self.analyzer = GapAnalyzer()

    def _make_report(self, covered_ops=None, covered_crosses=None):
        """Helper to create a report with specific coverage."""
        report = CoverageReport()
        op_cp = Coverpoint(name="op_code")
        all_ops = ["add", "sub", "mul", "div", "anding", "xoring"]
        covered_ops = covered_ops or []
        for op in all_ops:
            is_cov = op in covered_ops
            op_cp.bins.append(
                CoverageBin(op, hits=10 if is_cov else 0, is_covered=is_cov)
            )
        report.coverpoints["op_code"] = op_cp

        a_cp = Coverpoint(name="A")
        a_cp.bins = [
            CoverageBin("All_Ones", hits=10, is_covered=True),
            CoverageBin("All_Zeros", hits=10, is_covered=True),
            CoverageBin("random_stimulus", hits=100, is_covered=True),
        ]
        report.coverpoints["A"] = a_cp

        cross = CrossCoverage(name="corner_cases")
        all_crosses = [
            "Add_cross1", "Add_cross2", "Sub_cross1", "Sub_cross2",
            "Mul_cross1", "Mul_cross2", "Div_cross1", "Div_cross2",
            "And_cross1", "And_cross2", "Xor_cross1", "Xor_cross2",
        ]
        covered_crosses = covered_crosses or []
        for c in all_crosses:
            is_cov = c in covered_crosses
            cross.bins.append(
                CoverageBin(c, hits=5 if is_cov else 0, is_covered=is_cov)
            )
        report.crosses["corner_cases"] = cross

        report.compute_overall()
        return report

    def test_analyze_full_coverage(self):
        report = self._make_report(
            covered_ops=["add", "sub", "mul", "div", "anding", "xoring"],
            covered_crosses=[
                "Add_cross1", "Add_cross2", "Sub_cross1", "Sub_cross2",
                "Mul_cross1", "Mul_cross2", "Div_cross1", "Div_cross2",
                "And_cross1", "And_cross2", "Xor_cross1", "Xor_cross2",
            ],
        )
        analysis = self.analyzer.analyze(report)
        assert analysis.total_uncovered == 0
        assert "COMPLETE" in analysis.suggested_strategy

    def test_analyze_partial_coverage(self):
        report = self._make_report(
            covered_ops=["add", "sub"],
            covered_crosses=["Add_cross1"],
        )
        analysis = self.analyzer.analyze(report)
        assert analysis.total_uncovered > 0
        assert len(analysis.gaps) > 0

    def test_gap_priority(self):
        report = self._make_report(covered_ops=["add"])
        analysis = self.analyzer.analyze(report)
        # Cross coverage gaps should have higher priority
        cross_gaps = [g for g in analysis.gaps if g.coverpoint == "corner_cases"]
        cp_gaps = [g for g in analysis.gaps if g.coverpoint != "corner_cases"]
        if cross_gaps and cp_gaps:
            assert max(g.priority for g in cross_gaps) >= min(g.priority for g in cp_gaps)

    def test_suggested_values(self):
        report = self._make_report(covered_ops=[])
        analysis = self.analyzer.analyze(report)
        add_gap = next(
            (g for g in analysis.gaps if g.bin_name == "add"), None
        )
        assert add_gap is not None
        assert add_gap.suggested_values.get("op_code") == 0

    def test_stimulus_hints(self):
        report = self._make_report(covered_ops=["add", "sub"])
        analysis = self.analyzer.analyze(report)
        hints = analysis.stimulus_hints
        assert "target_opcodes" in hints
        # Missing opcodes should be in hints
        assert 2 in hints["target_opcodes"]  # mul
        assert 3 in hints["target_opcodes"]  # div

    def test_stagnation_detection(self):
        # Create 4 reports with same coverage to trigger stagnation
        report = self._make_report(covered_ops=["add", "sub"])
        for _ in range(4):
            self.analyzer.analyze(report)
        analysis = self.analyzer.analyze(report)
        assert analysis.stagnation_detected

    def test_coverage_trend(self):
        r1 = self._make_report(covered_ops=["add"])
        r2 = self._make_report(covered_ops=["add", "sub"])
        self.analyzer.analyze(r1)
        self.analyzer.analyze(r2)
        trend = self.analyzer.get_coverage_trend()
        assert len(trend) == 2
        assert trend[1] >= trend[0]
