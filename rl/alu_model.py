"""Reference ALU model mirroring the SystemVerilog DUT.

The UVM scoreboard uses an identical reference; this pure-Python copy lets us
train RL offline without spinning up a Verilog simulator for every step.
"""

from __future__ import annotations

from dataclasses import dataclass


OP_ADD = 0
OP_SUB = 1
OP_MUL = 2
OP_DIV = 3
OP_AND = 4
OP_XOR = 5

OP_NAMES = {
    OP_ADD: "ADD",
    OP_SUB: "SUB",
    OP_MUL: "MUL",
    OP_DIV: "DIV",
    OP_AND: "AND",
    OP_XOR: "XOR",
}


@dataclass
class AluInputs:
    a: int
    b: int
    op: int
    c_in: int = 0
    reset: int = 0

    def __post_init__(self) -> None:
        self.a = int(self.a) & 0xFF
        self.b = int(self.b) & 0xFF
        self.op = int(self.op) & 0xF
        self.c_in = int(self.c_in) & 0x1
        self.reset = int(self.reset) & 0x1


@dataclass
class AluOutputs:
    result: int
    c_out: int
    z_flag: int


def alu_model(inp: AluInputs) -> AluOutputs:
    """Combinational ALU reference model."""
    if inp.reset:
        return AluOutputs(result=0, c_out=0, z_flag=1)

    a, b, op, cin = inp.a, inp.b, inp.op, inp.c_in
    c_out = 0

    if op == OP_ADD:
        r = a + b + cin
        c_out = (r >> 8) & 1
    elif op == OP_SUB:
        r = (a - b) & 0xFFFF
        c_out = (r >> 8) & 1
    elif op == OP_MUL:
        r = (a * b) & 0xFFFF
    elif op == OP_DIV:
        r = 0 if b == 0 else (a // b)
    elif op == OP_AND:
        r = a & b
    elif op == OP_XOR:
        r = a ^ b
    else:
        r = 0

    r &= 0xFFFF
    z = 1 if r == 0 else 0
    return AluOutputs(result=r, c_out=int(c_out), z_flag=int(z))
