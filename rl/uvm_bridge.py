"""PyHDL-IF @hdl_if.api class loaded by VCS at simulation time.

The SV testbench instantiates two TLM FIFOs; PyHDL-IF exposes get/put
handles to them on the Python side. This module wires those handles to
thread-safe queues so that the RL agent running in another thread can talk
to the simulator without blocking the hdl_if event loop.

The class below is deliberately tolerant to the pyhdl-if API evolving - if
the ``@hdl_if.api`` decorator is unavailable (e.g. when running unit tests
without a simulator) the module imports cleanly and the class becomes a
pure-Python stub usable by :class:`rl.bridge_env.AluBridgeEnv`.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only under VCS
    import hdl_if  # type: ignore

    _HAS_HDL_IF = True
except Exception:  # pragma: no cover
    hdl_if = None  # type: ignore
    _HAS_HDL_IF = False


class _RingBridge:
    """Thread-safe request/response queues used by both sides."""

    def __init__(self, size: int = 256) -> None:
        self.req_q: "queue.Queue[int]" = queue.Queue(maxsize=size)
        self.rsp_q: "queue.Queue[int]" = queue.Queue(maxsize=size)


_BRIDGE_SINGLETON: Optional[_RingBridge] = None


def get_bridge() -> _RingBridge:
    """Return (creating if needed) the process-wide bridge queues."""
    global _BRIDGE_SINGLETON
    if _BRIDGE_SINGLETON is None:
        _BRIDGE_SINGLETON = _RingBridge(
            size=int(os.getenv("ALU_RL_BRIDGE_SIZE", "256"))
        )
    return _BRIDGE_SINGLETON


# ---------------------------------------------------------------------------
# Simulator-facing API
# ---------------------------------------------------------------------------
if _HAS_HDL_IF:

    @hdl_if.api  # type: ignore[misc]
    class UvmBridge:
        """Hooks exposed to the UVM bridge component.

        The SV side uses the TLM FIFOs directly; this class offers an
        additional control channel (start/stop/sync) so the Python driver
        thread can coordinate with the simulator phase machine.
        """

        def __init__(self, max_items: int = 1000):
            self._max_items = max_items
            self._started = threading.Event()
            self._bridge = get_bridge()

        # Called from UVM at run_phase to let Python know the sim is ready.
        @hdl_if.exp  # type: ignore[misc]
        def notify_started(self) -> None:
            log.info("UVM notified Python bridge: simulation started")
            self._started.set()

        # Called by UVM to announce end-of-simulation.
        @hdl_if.exp  # type: ignore[misc]
        def notify_finished(self, n_items: int, n_timeouts: int) -> None:
            log.info("UVM simulation finished: items=%d timeouts=%d",
                     n_items, n_timeouts)

        # Called by UVM when it wants a stimulus right away but the Python
        # queue is empty (rare - normally the SV side polls the FIFO).
        @hdl_if.imp  # type: ignore[misc]
        def pop_request_blocking(self, timeout_ms: int) -> int:
            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                try:
                    return self._bridge.req_q.get(timeout=0.05)
                except queue.Empty:
                    continue
            return 0  # timeout - SV side will inject a random fallback

        # Called by UVM to deliver a response payload to Python.
        @hdl_if.imp  # type: ignore[misc]
        def push_response(self, payload: int) -> None:
            try:
                self._bridge.rsp_q.put_nowait(int(payload))
            except queue.Full:
                log.warning("response queue full; dropping payload")

else:  # pragma: no cover - simulator-less fallback

    class UvmBridge:  # type: ignore[no-redef]
        """Stub used when pyhdl-if is not importable."""

        def __init__(self, max_items: int = 1000) -> None:
            self._max_items = max_items
            self._bridge = get_bridge()

        def notify_started(self) -> None:  # noqa: D401
            """No-op in stub mode."""

        def notify_finished(self, n_items: int, n_timeouts: int) -> None:
            pass

        def pop_request_blocking(self, timeout_ms: int) -> int:
            try:
                return self._bridge.req_q.get(timeout=timeout_ms / 1000.0)
            except queue.Empty:
                return 0

        def push_response(self, payload: int) -> None:
            try:
                self._bridge.rsp_q.put_nowait(int(payload))
            except queue.Full:
                log.warning("response queue full; dropping payload")
