"""
Python simulation model of the 8-bit ALU and its UVM coverage collector.

This model faithfully replicates the DUT behaviour and coverage bins defined in
the original UVM testbench so that RL agents can be trained purely in Python
without requiring a Synopsys VCS licence.  When VCS is available, the
orchestrator swaps this model for live simulation data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# ALU functional model
# ---------------------------------------------------------------------------

@dataclass
class ALUTransaction:
    """Mirrors ALU_Sequence_Item fields."""
    a: int = 0
    b: int = 0
    opcode: int = 0
    c_in: int = 0
    reset: int = 0
    result: int = 0
    c_out: int = 0
    z_flag: int = 0


class ALUModel:
    """Cycle-accurate Python model of the 8-bit ALU DUT."""

    OP_ADD  = 0
    OP_SUB  = 1
    OP_MULT = 2
    OP_DIV  = 3
    OP_AND  = 4
    OP_XOR  = 5
    VALID_OPCODES = range(6)

    def execute(self, a: int, b: int, opcode: int, c_in: int = 0) -> ALUTransaction:
        a &= 0xFF
        b &= 0xFF
        opcode &= 0xF
        c_in &= 0x1
        txn = ALUTransaction(a=a, b=b, opcode=opcode, c_in=c_in, reset=0)

        if opcode == self.OP_ADD:
            temp = a + b + c_in
            c_out = (temp >> 8) & 1
        elif opcode == self.OP_SUB:
            temp = a - b
            c_out = (temp >> 8) & 1
        elif opcode == self.OP_MULT:
            temp = a * b
            c_out = 0
        elif opcode == self.OP_DIV:
            temp = (a // b) if b != 0 else 0
            c_out = 0
        elif opcode == self.OP_AND:
            temp = a & b
            c_out = 0
        elif opcode == self.OP_XOR:
            temp = a ^ b
            c_out = 0
        else:
            temp = 0
            c_out = 0

        result = temp & 0xFFFF
        z_flag = 1 if result == 0 else 0

        txn.result = result
        txn.c_out = c_out
        txn.z_flag = z_flag
        return txn


# ---------------------------------------------------------------------------
# Coverage model  –  mirrors ALU_Coverage_Collector.sv
# ---------------------------------------------------------------------------

class CoverageModel:
    """
    Tracks functional coverage bins identical to the UVM covergroup.

    Bin layout (28 total):
        A           : All_Ones, All_Zeros, random_stimulus   (3)
        B           : All_Ones, All_Zeros, random_stimulus   (3)
        op_code     : add, sub, mul, div, anding, xoring     (6)
        C_in        : 0, 1                                   (2)
        Reset       : 0, 1                                   (2)
        corner_cases: {Add,Sub,Mul,Div,And,Xor} x {cross1, cross2}  (12)
    """

    BIN_NAMES: list[str] = [
        # A bins (0-2)
        "A_All_Ones", "A_All_Zeros", "A_random",
        # B bins (3-5)
        "B_All_Ones", "B_All_Zeros", "B_random",
        # op_code bins (6-11)
        "op_add", "op_sub", "op_mul", "op_div", "op_and", "op_xor",
        # C_in bins (12-13)
        "C_in_0", "C_in_1",
        # Reset bins (14-15)
        "Reset_0", "Reset_1",
        # Corner-case cross bins (16-27)
        "Add_cross1", "Add_cross2",
        "Sub_cross1", "Sub_cross2",
        "Mul_cross1", "Mul_cross2",
        "Div_cross1", "Div_cross2",
        "And_cross1", "And_cross2",
        "Xor_cross1", "Xor_cross2",
    ]

    NUM_BINS = len(BIN_NAMES)
    _OP_CROSS_OFFSET = {0: 16, 1: 18, 2: 20, 3: 22, 4: 24, 5: 26}

    def __init__(self) -> None:
        self.hit_count = np.zeros(self.NUM_BINS, dtype=np.int64)

    # -- sampling ---------------------------------------------------------

    def sample(self, txn: ALUTransaction) -> None:
        a, b, op, c_in, rst = txn.a, txn.b, txn.opcode, txn.c_in, txn.reset

        # A bins
        if a == 0xFF:
            self.hit_count[0] += 1
        elif a == 0x00:
            self.hit_count[1] += 1
        else:
            self.hit_count[2] += 1

        # B bins
        if b == 0xFF:
            self.hit_count[3] += 1
        elif b == 0x00:
            self.hit_count[4] += 1
        else:
            self.hit_count[5] += 1

        # op_code bins
        if 0 <= op <= 5:
            self.hit_count[6 + op] += 1

        # C_in bins
        self.hit_count[12 + (c_in & 1)] += 1

        # Reset bins
        self.hit_count[14 + (rst & 1)] += 1

        # Corner-case cross bins  (A x B x op)
        if op in self._OP_CROSS_OFFSET:
            base = self._OP_CROSS_OFFSET[op]
            if a == 0xFF and b == 0xFF:
                self.hit_count[base] += 1      # cross1
            if a == 0x00 and b == 0x00:
                self.hit_count[base + 1] += 1  # cross2

    # -- queries ----------------------------------------------------------

    @property
    def covered_vector(self) -> np.ndarray:
        return (self.hit_count > 0).astype(np.float32)

    @property
    def total_covered(self) -> int:
        return int(np.sum(self.hit_count > 0))

    @property
    def coverage_percentage(self) -> float:
        return float(self.total_covered / self.NUM_BINS * 100.0)

    @property
    def uncovered_bins(self) -> list[str]:
        return [n for n, c in zip(self.BIN_NAMES, self.hit_count) if c == 0]

    @property
    def uncovered_indices(self) -> list[int]:
        return [i for i, c in enumerate(self.hit_count) if c == 0]

    def get_state_vector(self) -> np.ndarray:
        cov_vec = self.covered_vector
        overall = np.array(
            [self.coverage_percentage / 100.0], dtype=np.float32
        )
        return np.concatenate([cov_vec, overall])

    def reset(self) -> None:
        self.hit_count[:] = 0

    def merge(self, other: "CoverageModel") -> None:
        self.hit_count = np.maximum(self.hit_count, other.hit_count)

    def copy(self) -> "CoverageModel":
        c = CoverageModel()
        c.hit_count = self.hit_count.copy()
        return c


# ---------------------------------------------------------------------------
# Stimulus generator that mirrors UVM constrained-random with seed control
# ---------------------------------------------------------------------------

class StimulusGenerator:
    """
    Generates ALU transactions using the same distribution style as the UVM
    testbench ``ALU_Sequence_Item`` constraints, controlled by a random seed.

    Original UVM constraints:
        op_code inside {[0:5]}
        A dist { 0xFF := 80, 0x00 := 80, [0x01:0xFE] := 10 }
        B dist { 0xFF := 80, 0x00 := 80, [0x01:0xFE] := 10 }
    """

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)

    def set_seed(self, seed: int) -> None:
        seed = int(seed)
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed % (2**31))

    def generate_default(self, n: int = 1) -> list[ALUTransaction]:
        """Unconstrained random — mirrors the default UVM sequence."""
        txns: list[ALUTransaction] = []
        for _ in range(n):
            a = self._sample_operand_default()
            b = self._sample_operand_default()
            op = self.rng.randint(0, 5)
            c_in = self.rng.randint(0, 1)
            txns.append(ALUTransaction(a=a, b=b, opcode=op, c_in=c_in, reset=0))
        return txns

    def generate_biased(
        self,
        n: int,
        opcode_weights: Optional[list[float]] = None,
        operand_bias: str = "default",
    ) -> list[ALUTransaction]:
        """
        Generate transactions with AI-controlled bias.

        Parameters
        ----------
        opcode_weights : list of 6 floats (normalised internally)
        operand_bias   : 'default' | 'zeros' | 'ones' | 'boundary' | 'uniform'
        """
        txns: list[ALUTransaction] = []

        if opcode_weights is None:
            opcode_weights = [1.0] * 6
        w = np.array(opcode_weights, dtype=np.float64)
        w = w / w.sum()

        for _ in range(n):
            a = self._sample_operand(operand_bias)
            b = self._sample_operand(operand_bias)
            op = int(self.np_rng.choice(6, p=w))
            c_in = self.rng.randint(0, 1)
            txns.append(ALUTransaction(a=a, b=b, opcode=op, c_in=c_in, reset=0))
        return txns

    # -- internal helpers -------------------------------------------------

    def _sample_operand_default(self) -> int:
        """Mirrors UVM dist { 0xFF := 80, 0x00 := 80, [0x01:0xFE] := 10 }.

        UVM `:=` assigns the weight to *each* value in the range, so
        [0x01:0xFE] has 254 items each with weight 10 → total 2540.
        Total weight = 80 + 80 + 254*10 = 2700.
        P(0xFF) ≈ 2.96%, P(0x00) ≈ 2.96%, P(random) ≈ 94.07%.
        """
        r = self.rng.random()
        # Per-item weights: 0xFF=80, 0x00=80, each of [0x01..0xFE]=10
        total = 80 + 80 + 254 * 10  # = 2700
        if r < 80 / total:
            return 0xFF
        elif r < 160 / total:
            return 0x00
        else:
            return self.rng.randint(0x01, 0xFE)

    def _sample_operand(self, bias: str) -> int:
        if bias == "zeros":
            return 0x00 if self.rng.random() < 0.7 else self._sample_operand_default()
        elif bias == "ones":
            return 0xFF if self.rng.random() < 0.7 else self._sample_operand_default()
        elif bias == "boundary":
            r = self.rng.random()
            if r < 0.35:
                return 0x00
            elif r < 0.70:
                return 0xFF
            else:
                return self.rng.randint(0x01, 0xFE)
        elif bias == "uniform":
            return self.rng.randint(0x00, 0xFF)
        else:
            return self._sample_operand_default()


# ---------------------------------------------------------------------------
# Full simulation runner (Python-only mode)
# ---------------------------------------------------------------------------

class PythonSimRunner:
    """
    Runs a batch of transactions through the Python ALU model and accumulates
    coverage.  Acts as the drop-in replacement for VCS when training offline.
    """

    def __init__(self) -> None:
        self.alu = ALUModel()
        self.coverage = CoverageModel()
        self.total_transactions = 0

    def run_batch(self, transactions: list[ALUTransaction]) -> float:
        """Execute transactions, return coverage percentage after batch."""
        for txn in transactions:
            out = self.alu.execute(txn.a, txn.b, txn.opcode, txn.c_in)
            txn.result = out.result
            txn.c_out = out.c_out
            txn.z_flag = out.z_flag
            self.coverage.sample(txn)
            self.total_transactions += 1
        return self.coverage.coverage_percentage

    def reset(self) -> None:
        self.coverage.reset()
        self.total_transactions = 0

    def get_coverage_state(self) -> np.ndarray:
        return self.coverage.get_state_vector()
