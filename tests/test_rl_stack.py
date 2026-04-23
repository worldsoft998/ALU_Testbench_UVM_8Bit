"""Fast unit tests for the Python RL stack (no simulator required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from rl.alu_env import AluCoverageEnv
from rl.alu_model import AluInputs, alu_model
from rl.bridge_env import pack_request, unpack_response
from rl.coverage_model import CoverageModel


def test_alu_model_basic():
    out = alu_model(AluInputs(a=0x20, b=0x10, op=0))      # ADD
    assert out.result == 0x30 and out.c_out == 0 and out.z_flag == 0
    out = alu_model(AluInputs(a=0xFF, b=0xFF, op=2))      # MUL
    assert out.result == (0xFF * 0xFF) & 0xFFFF
    out = alu_model(AluInputs(a=5, b=0, op=3))            # DIV-by-0 guard
    assert out.result == 0


def test_coverage_model_bins():
    cm = CoverageModel()
    assert cm.hit_bins == 0
    new = cm.sample(reset=0, c_in=0, op=0, a=0, b=0)
    assert new > 0 and cm.coverage > 0


def test_env_runs_200_steps():
    env = AluCoverageEnv(max_steps=200)
    obs, _ = env.reset(seed=0)
    assert obs.shape[0] > 0
    total = 0.0
    for _ in range(200):
        a = env.action_space.sample()
        obs, r, term, trunc, info = env.step(a)
        total += float(r)
        if term or trunc:
            break
    assert info["coverage_pct"] > 0


def test_pack_unpack_roundtrip():
    payload = pack_request(reset=1, c_in=1, op=5, a=0xA5, b=0x5A, eoe=0, gen_id=0xDEADBEEF)
    # Simulate SV-side re-pack as response.
    rsp = 0
    rsp |= (0x1234 & 0xFFFF) << 0
    rsp |= 1 << 16
    rsp |= 0 << 17
    rsp |= 0 << 18
    rsp |= 1 << 19
    rsp |= (77 & 0xFF) << 20
    rsp |= (5 & 0xF) << 28
    rsp |= (0xDEADBEEF & 0xFFFFFFFF) << 32
    dec = unpack_response(rsp)
    assert dec.result == 0x1234 and dec.c_out == 1 and dec.reset == 1
    assert dec.cov_pct == 77 and dec.op_code == 5 and dec.gen_id == 0xDEADBEEF
    # The round-trip invariant only holds for bits we re-read.
    assert (payload >> 32) == 0xDEADBEEF


if __name__ == "__main__":
    test_alu_model_basic()
    test_coverage_model_bins()
    test_env_runs_200_steps()
    test_pack_unpack_roundtrip()
    print("ALL OK")
