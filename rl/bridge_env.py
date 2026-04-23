"""Gymnasium env that drives stimulus into a live UVM simulation via PyHDL-IF.

Used when the RL agent runs *online*, stepping a VCS simulation with real
RTL coverage feedback. When PyHDL-IF is not available or the bridge is not
started, the env transparently falls back to :class:`AluCoverageEnv` so the
unit tests keep working in CI.
"""

from __future__ import annotations

import logging
import queue
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .alu_env import AluCoverageEnv
from .coverage_model import CoverageModel

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Request/response packing - mirrors the SV bridge in tb_rl/bridge/alu_rl_bridge.sv
# -----------------------------------------------------------------------------
def pack_request(
    *, reset: int, c_in: int, op: int, a: int, b: int, eoe: int = 0, gen_id: int = 0,
) -> int:
    payload = 0
    payload |= (reset & 0x1) << 0
    payload |= (c_in & 0x1) << 1
    payload |= (op & 0xF) << 2
    payload |= (a & 0xFF) << 6
    payload |= (b & 0xFF) << 14
    payload |= (eoe & 0x1) << 22
    payload |= (gen_id & 0xFFFFFFFF) << 32
    return payload & ((1 << 64) - 1)


@dataclass
class DecodedResponse:
    result: int
    c_out: int
    z_flag: int
    mismatch: int
    reset: int
    cov_pct: int
    op_code: int
    gen_id: int


def unpack_response(payload: int) -> DecodedResponse:
    p = payload & ((1 << 64) - 1)
    return DecodedResponse(
        result=(p >> 0) & 0xFFFF,
        c_out=(p >> 16) & 0x1,
        z_flag=(p >> 17) & 0x1,
        mismatch=(p >> 18) & 0x1,
        reset=(p >> 19) & 0x1,
        cov_pct=(p >> 20) & 0xFF,
        op_code=(p >> 28) & 0xF,
        gen_id=(p >> 32) & 0xFFFFFFFF,
    )


# -----------------------------------------------------------------------------
# BridgeEnv
# -----------------------------------------------------------------------------
class AluBridgeEnv(gym.Env):
    """Step one stimulus against a live UVM simulation.

    Parameters
    ----------
    request_q / response_q :
        Thread-safe queues into which ``UvmBridge`` pushes/pulls payloads.
        When ``None`` the env falls back to the pure-Python ``AluCoverageEnv``.
    timeout_s :
        Hard timeout on a single step. If the simulator does not respond in
        time, the step is marked ``truncated`` with ``info["timeout"]``.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        request_q: Optional["queue.Queue[int]"] = None,
        response_q: Optional["queue.Queue[int]"] = None,
        max_steps: int = 1000,
        timeout_s: float = 2.0,
        target_coverage: float = 100.0,
    ) -> None:
        super().__init__()
        self._fallback = AluCoverageEnv(max_steps=max_steps, target_coverage=target_coverage)
        self.observation_space = self._fallback.observation_space
        self.action_space = self._fallback.action_space

        self.max_steps = int(max_steps)
        self.timeout_s = float(timeout_s)
        self.target_coverage = float(target_coverage)

        self.request_q = request_q
        self.response_q = response_q

        self._step_idx = 0
        self._cov = CoverageModel()
        self._last_sim_cov = 0.0
        self._timeouts = 0

    def _live(self) -> bool:
        return self.request_q is not None and self.response_q is not None

    # ---------------- gym api ----------------
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        if not self._live():
            return self._fallback.reset(seed=seed, options=options)
        self._cov = CoverageModel()
        self._step_idx = 0
        self._last_sim_cov = 0.0
        # Drain any stale responses
        while self.response_q is not None and not self.response_q.empty():
            try:
                self.response_q.get_nowait()
            except queue.Empty:
                break
        return self._obs(), {"coverage_pct": 0.0}

    def _obs(self) -> np.ndarray:
        mask = np.asarray(self._cov.hit_mask(), dtype=np.float32)
        cov = np.float32(self._cov.coverage / 100.0)
        progress = np.float32(self._step_idx / max(1, self.max_steps))
        return np.concatenate([mask, np.array([cov, progress], dtype=np.float32)])

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if not self._live():
            return self._fallback.step(action)

        op, a, b, cin, rst = (int(x) for x in action)
        payload = pack_request(
            reset=rst, c_in=cin, op=op, a=a, b=b, eoe=0, gen_id=self._step_idx,
        )
        self.request_q.put(payload)

        t0 = time.monotonic()
        try:
            rsp = self.response_q.get(timeout=self.timeout_s)
        except queue.Empty:
            self._timeouts += 1
            log.warning("bridge response timeout on step %d", self._step_idx)
            info = {"timeout": True, "coverage_pct": self._last_sim_cov}
            return self._obs(), -1.0, False, True, info

        decoded = unpack_response(rsp)
        new_hits = self._cov.sample(
            reset=decoded.reset, c_in=cin, op=op, a=a, b=b,
        )
        self._last_sim_cov = float(decoded.cov_pct)

        reward = float(new_hits)
        if new_hits == 0:
            reward -= 0.01
        if decoded.mismatch:
            # A real DUT bug was found - worth a big reward to the agent.
            reward += 5.0

        self._step_idx += 1
        terminated = self._cov.coverage >= self.target_coverage
        truncated = self._step_idx >= self.max_steps
        info = {
            "coverage_pct": self._cov.coverage,
            "sim_coverage_pct": self._last_sim_cov,
            "mismatch": bool(decoded.mismatch),
            "new_bins": new_hits,
            "rt_s": time.monotonic() - t0,
        }
        return self._obs(), reward, bool(terminated), bool(truncated), info

    def close(self) -> None:  # pragma: no cover - trivial
        if self._live():
            eoe = pack_request(reset=0, c_in=0, op=0, a=0, b=0, eoe=1)
            try:
                self.request_q.put_nowait(eoe)
            except queue.Full:
                pass
