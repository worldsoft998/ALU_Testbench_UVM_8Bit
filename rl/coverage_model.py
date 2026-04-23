"""Functional-coverage model that mirrors the SV coverage collector.

Bins are defined so that a 100% hit in Python is equivalent to a 100% hit in
the simulator's ``cg_alu`` covergroup. Keeping them in lock-step makes
coverage feedback from the UVM bridge directly comparable to offline
training reward signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


A_BINS = ("zero", "max", "low", "mid", "high")
B_BINS = ("zero", "max", "low", "mid", "high")
OP_BINS = ("add", "sub", "mul", "div", "andd", "xorr")
CIN_BINS = (0, 1)
RESET_BINS = (0, 1)


def _bin_ab(v: int) -> str:
    v &= 0xFF
    if v == 0x00:
        return "zero"
    if v == 0xFF:
        return "max"
    if v <= 0x3F:
        return "low"
    if v <= 0xBF:
        return "mid"
    return "high"


def _bin_op(op: int) -> str:
    op &= 0xF
    return {
        0: "add", 1: "sub", 2: "mul", 3: "div", 4: "andd", 5: "xorr",
    }.get(op, "add")


@dataclass
class CoveragePoint:
    name: str
    bins: Tuple[str, ...]


class CoverageModel:
    """Tracks hits for coverpoints + selected crosses.

    The bin set is enumerated up-front so total/hit accounting is exact.
    """

    def __init__(self) -> None:
        self._point_hits: Dict[str, Dict[object, int]] = {}
        # Define coverpoints
        for name, bins in [
            ("cp_reset", RESET_BINS),
            ("cp_cin", CIN_BINS),
            ("cp_A", A_BINS),
            ("cp_B", B_BINS),
            ("cp_op", OP_BINS),
        ]:
            self._point_hits[name] = {b: 0 for b in bins}

        # Crosses (kept small-ish to avoid blowing up the bin count)
        self._point_hits["cx_op_A"] = {(o, a): 0 for o in OP_BINS for a in A_BINS}
        self._point_hits["cx_op_B"] = {(o, b): 0 for o in OP_BINS for b in B_BINS}
        self._point_hits["cx_AB_corners"] = {
            ("zero", "zero"): 0,
            ("max", "max"): 0,
            ("zero", "max"): 0,
            ("max", "zero"): 0,
        }

        self._total_bins = sum(len(v) for v in self._point_hits.values())
        self._prev_hits = 0

    @property
    def total_bins(self) -> int:
        return self._total_bins

    def sample(self, reset: int, c_in: int, op: int, a: int, b: int) -> int:
        """Sample one stimulus; return number of NEW unique bins hit."""
        before = self.hit_bins
        self._point_hits["cp_reset"][int(reset) & 1] = (
            self._point_hits["cp_reset"][int(reset) & 1] + 1
        )
        self._point_hits["cp_cin"][int(c_in) & 1] = (
            self._point_hits["cp_cin"][int(c_in) & 1] + 1
        )
        ab = _bin_ab(a)
        bb = _bin_ab(b)
        ob = _bin_op(op)
        self._point_hits["cp_A"][ab] += 1
        self._point_hits["cp_B"][bb] += 1
        self._point_hits["cp_op"][ob] += 1
        self._point_hits["cx_op_A"][(ob, ab)] += 1
        self._point_hits["cx_op_B"][(ob, bb)] += 1
        key = (ab, bb)
        if key in self._point_hits["cx_AB_corners"]:
            self._point_hits["cx_AB_corners"][key] += 1
        after = self.hit_bins
        new = after - before
        self._prev_hits = after
        return new

    @property
    def hit_bins(self) -> int:
        return sum(
            1
            for group in self._point_hits.values()
            for count in group.values()
            if count > 0
        )

    @property
    def coverage(self) -> float:
        return 100.0 * self.hit_bins / self._total_bins

    def snapshot(self) -> Dict[str, float]:
        return {
            "coverage_pct": self.coverage,
            "hit_bins": self.hit_bins,
            "total_bins": self.total_bins,
        }

    def hit_mask(self) -> list[int]:
        """Flat 0/1 vector of every bin's hit status (for observation use)."""
        out: list[int] = []
        for group in self._point_hits.values():
            for count in group.values():
                out.append(1 if count > 0 else 0)
        return out
