"""
Analyze coverage gaps and produce actionable intelligence for the AI agent.
Maps uncovered bins to stimulus strategies.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .coverage_parser import CoverageReport

logger = logging.getLogger(__name__)


@dataclass
class CoverageGap:
    """A specific coverage gap with analysis."""
    coverpoint: str
    bin_name: str
    hits: int
    priority: float  # 0.0 (low) to 1.0 (critical)
    suggested_values: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class GapAnalysis:
    """Complete gap analysis result."""
    gaps: list = field(default_factory=list)
    total_uncovered: int = 0
    total_bins: int = 0
    coverage_pct: float = 0.0
    stagnation_detected: bool = False
    suggested_strategy: str = ""
    stimulus_hints: dict = field(default_factory=dict)


# Mapping from coverage bins to specific ALU input values
ALU_BIN_TO_VALUES = {
    # A coverpoint bins
    ("A", "All_Ones"): {"A": 0xFF},
    ("A", "All_Zeros"): {"A": 0x00},
    ("A", "random_stimulus"): {"A": "random_mid_range"},
    # B coverpoint bins
    ("B", "All_Ones"): {"B": 0xFF},
    ("B", "All_Zeros"): {"B": 0x00},
    ("B", "random_stimulus"): {"B": "random_mid_range"},
    # op_code bins
    ("op_code", "add"): {"op_code": 0},
    ("op_code", "sub"): {"op_code": 1},
    ("op_code", "mul"): {"op_code": 2},
    ("op_code", "div"): {"op_code": 3},
    ("op_code", "anding"): {"op_code": 4},
    ("op_code", "xoring"): {"op_code": 5},
    # C_in bins
    ("C_in", "0"): {"C_in": 0},
    ("C_in", "1"): {"C_in": 1},
    # Reset bins
    ("Reset", "0"): {"Reset": 0},
    ("Reset", "1"): {"Reset": 1},
    # Corner case cross bins
    ("corner_cases", "Add_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 0},
    ("corner_cases", "Add_cross2"): {"A": 0x00, "B": 0x00, "op_code": 0},
    ("corner_cases", "Sub_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 1},
    ("corner_cases", "Sub_cross2"): {"A": 0x00, "B": 0x00, "op_code": 1},
    ("corner_cases", "Mul_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 2},
    ("corner_cases", "Mul_cross2"): {"A": 0x00, "B": 0x00, "op_code": 2},
    ("corner_cases", "Div_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 3},
    ("corner_cases", "Div_cross2"): {"A": 0x00, "B": 0x00, "op_code": 3},
    ("corner_cases", "And_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 4},
    ("corner_cases", "And_cross2"): {"A": 0x00, "B": 0x00, "op_code": 4},
    ("corner_cases", "Xor_cross1"): {"A": 0xFF, "B": 0xFF, "op_code": 5},
    ("corner_cases", "Xor_cross2"): {"A": 0x00, "B": 0x00, "op_code": 5},
}


class GapAnalyzer:
    """Analyze coverage reports to identify gaps and recommend stimulus strategies."""

    def __init__(self):
        self._history: list = []

    def analyze(self, report: CoverageReport) -> GapAnalysis:
        """Analyze a coverage report and identify gaps with priorities."""
        analysis = GapAnalysis()
        analysis.coverage_pct = report.overall_coverage

        total_bins = 0
        covered_bins = 0

        # Analyze coverpoints
        for cp_name, cp in report.coverpoints.items():
            for b in cp.bins:
                total_bins += 1
                if b.is_covered:
                    covered_bins += 1
                else:
                    gap = self._create_gap(cp_name, b.name, b.hits)
                    analysis.gaps.append(gap)

        # Analyze cross coverage
        for cr_name, cr in report.crosses.items():
            for b in cr.bins:
                total_bins += 1
                if b.is_covered:
                    covered_bins += 1
                else:
                    gap = self._create_gap(cr_name, b.name, b.hits)
                    gap.priority = min(1.0, gap.priority + 0.2)  # Cross bins are higher priority
                    analysis.gaps.append(gap)

        analysis.total_bins = total_bins
        analysis.total_uncovered = len(analysis.gaps)

        # Sort gaps by priority (highest first)
        analysis.gaps.sort(key=lambda g: g.priority, reverse=True)

        # Detect stagnation
        analysis.stagnation_detected = self._detect_stagnation(report)

        # Generate strategy
        analysis.suggested_strategy = self._suggest_strategy(analysis)
        analysis.stimulus_hints = self._generate_stimulus_hints(analysis)

        self._history.append(analysis)
        return analysis

    def _create_gap(self, coverpoint: str, bin_name: str, hits: int) -> CoverageGap:
        """Create a coverage gap with analysis."""
        priority = 0.5
        if hits == 0:
            priority = 1.0
        elif hits < 3:
            priority = 0.8

        # Cross coverage bins get higher priority
        if coverpoint == "corner_cases":
            priority = min(1.0, priority + 0.1)

        values = ALU_BIN_TO_VALUES.get((coverpoint, bin_name), {})
        description = self._describe_gap(coverpoint, bin_name, hits)

        return CoverageGap(
            coverpoint=coverpoint,
            bin_name=bin_name,
            hits=hits,
            priority=priority,
            suggested_values=values,
            description=description,
        )

    def _describe_gap(self, coverpoint: str, bin_name: str, hits: int) -> str:
        """Generate human-readable gap description."""
        if coverpoint == "corner_cases":
            parts = bin_name.split("_")
            op = parts[0]
            variant = parts[1] if len(parts) > 1 else ""
            if variant == "cross1":
                return f"{op} operation with both operands = 0xFF (boundary max)"
            elif variant == "cross2":
                return f"{op} operation with both operands = 0x00 (boundary min)"
        elif coverpoint in ("A", "B"):
            if bin_name == "All_Ones":
                return f"Operand {coverpoint} = 0xFF (all ones)"
            elif bin_name == "All_Zeros":
                return f"Operand {coverpoint} = 0x00 (all zeros)"
        elif coverpoint == "op_code":
            op_names = {
                "add": "Addition (0)", "sub": "Subtraction (1)",
                "mul": "Multiplication (2)", "div": "Division (3)",
                "anding": "AND (4)", "xoring": "XOR (5)",
            }
            return f"Operation: {op_names.get(bin_name, bin_name)}"
        return f"{coverpoint}.{bin_name} (hits={hits})"

    def _detect_stagnation(self, report: CoverageReport) -> bool:
        """Detect if coverage has stagnated."""
        if len(self._history) < 3:
            return False
        recent = [h.coverage_pct for h in self._history[-3:]]
        max_delta = max(recent) - min(recent)
        return max_delta < 0.5

    def _suggest_strategy(self, analysis: GapAnalysis) -> str:
        """Suggest a high-level verification strategy."""
        if analysis.total_uncovered == 0:
            return "COMPLETE: All coverage bins are hit."

        cross_gaps = [g for g in analysis.gaps if g.coverpoint == "corner_cases"]
        cp_gaps = [g for g in analysis.gaps if g.coverpoint != "corner_cases"]

        parts = []
        if cross_gaps:
            ops_missing = set()
            for g in cross_gaps:
                op = g.bin_name.split("_")[0]
                ops_missing.add(op)
            parts.append(
                f"Target corner cases: {', '.join(sorted(ops_missing))} "
                f"operations with boundary values (0x00, 0xFF)."
            )
        if cp_gaps:
            cps = set(g.coverpoint for g in cp_gaps)
            parts.append(f"Cover missing bins in: {', '.join(sorted(cps))}.")

        if analysis.stagnation_detected:
            parts.append(
                "STAGNATION DETECTED: Switch to targeted seeds or "
                "increase transaction count."
            )

        return " ".join(parts)

    def _generate_stimulus_hints(self, analysis: GapAnalysis) -> dict:
        """Generate specific stimulus parameter hints for the AI agent."""
        hints = {
            "target_A_values": set(),
            "target_B_values": set(),
            "target_opcodes": set(),
            "target_C_in": set(),
            "priority_level": "normal",
        }

        for gap in analysis.gaps:
            vals = gap.suggested_values
            if "A" in vals and isinstance(vals["A"], int):
                hints["target_A_values"].add(vals["A"])
            if "B" in vals and isinstance(vals["B"], int):
                hints["target_B_values"].add(vals["B"])
            if "op_code" in vals:
                hints["target_opcodes"].add(vals["op_code"])
            if "C_in" in vals:
                hints["target_C_in"].add(vals["C_in"])

        # Convert sets to sorted lists for serialization
        hints["target_A_values"] = sorted(hints["target_A_values"])
        hints["target_B_values"] = sorted(hints["target_B_values"])
        hints["target_opcodes"] = sorted(hints["target_opcodes"])
        hints["target_C_in"] = sorted(hints["target_C_in"])

        if analysis.stagnation_detected:
            hints["priority_level"] = "high"
        elif analysis.total_uncovered > 5:
            hints["priority_level"] = "elevated"

        return hints

    def get_coverage_trend(self) -> list:
        """Return historical coverage percentages."""
        return [h.coverage_pct for h in self._history]

    def get_gap_trend(self) -> list:
        """Return historical uncovered bin counts."""
        return [h.total_uncovered for h in self._history]
