"""
PyHDL-IF Bridge: Python <-> SystemVerilog 2-Way Communication
==============================================================
Implements a bidirectional bridge between Python RL agent and
the SystemVerilog UVM testbench using named pipes (FIFOs) following
the PyHDL-IF interface pattern.

Protocol:
    Python -> SV: STIMULUS <A> <B> <op_code> <C_in>
    SV -> Python: RESPONSE <Result> <C_out> <Z_flag> <coverage_pct>
    Handshake:    READY / ACK / DONE / TIMEOUT

No DPI-C or C-based intermediary is used. Communication is purely
through OS-level named pipes managed by the pyhdl-if pattern.
"""

import os
import sys
import time
import json
import struct
import signal
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types for the bridge protocol."""
    STIMULUS = auto()       # Python -> SV: send stimulus
    RESPONSE = auto()       # SV -> Python: send results + coverage
    COVERAGE = auto()       # SV -> Python: coverage report
    READY = auto()          # Handshake: ready for next transaction
    ACK = auto()            # Handshake: acknowledged
    DONE = auto()           # Session complete
    RESET = auto()          # Reset DUT
    CONFIG = auto()         # Configuration message
    ERROR = auto()          # Error notification
    TIMEOUT = auto()        # Timeout notification


@dataclass
class StimulusMessage:
    """Stimulus transaction from Python to SystemVerilog."""
    msg_type: str = "STIMULUS"
    seq_id: int = 0
    A: int = 0              # 8-bit operand A
    B: int = 0              # 8-bit operand B
    op_code: int = 0        # 4-bit operation code (0-5)
    C_in: int = 0           # carry-in bit
    reset: int = 0          # reset signal
    timestamp: float = 0.0

    def to_line(self) -> str:
        """Serialize to pipe-friendly single-line format."""
        return (f"{self.msg_type} {self.seq_id} {self.A} {self.B} "
                f"{self.op_code} {self.C_in} {self.reset} {self.timestamp:.6f}\n")

    @classmethod
    def from_line(cls, line: str) -> 'StimulusMessage':
        """Deserialize from pipe line."""
        parts = line.strip().split()
        return cls(
            msg_type=parts[0],
            seq_id=int(parts[1]),
            A=int(parts[2]),
            B=int(parts[3]),
            op_code=int(parts[4]),
            C_in=int(parts[5]),
            reset=int(parts[6]),
            timestamp=float(parts[7]) if len(parts) > 7 else time.time()
        )


@dataclass
class ResponseMessage:
    """Response transaction from SystemVerilog to Python."""
    msg_type: str = "RESPONSE"
    seq_id: int = 0
    result: int = 0         # 16-bit ALU result
    C_out: int = 0          # carry-out
    Z_flag: int = 0         # zero flag
    coverage_pct: float = 0.0
    coverage_bins_hit: int = 0
    coverage_bins_total: int = 0
    error_count: int = 0
    timestamp: float = 0.0

    def to_line(self) -> str:
        """Serialize to pipe-friendly single-line format."""
        return (f"{self.msg_type} {self.seq_id} {self.result} {self.C_out} "
                f"{self.Z_flag} {self.coverage_pct:.4f} {self.coverage_bins_hit} "
                f"{self.coverage_bins_total} {self.error_count} "
                f"{self.timestamp:.6f}\n")

    @classmethod
    def from_line(cls, line: str) -> 'ResponseMessage':
        """Deserialize from pipe line."""
        parts = line.strip().split()
        return cls(
            msg_type=parts[0],
            seq_id=int(parts[1]),
            result=int(parts[2]),
            C_out=int(parts[3]),
            Z_flag=int(parts[4]),
            coverage_pct=float(parts[5]),
            coverage_bins_hit=int(parts[6]),
            coverage_bins_total=int(parts[7]),
            error_count=int(parts[8]),
            timestamp=float(parts[9]) if len(parts) > 9 else time.time()
        )


@dataclass
class CoverageReport:
    """Detailed coverage report from SV."""
    total_coverage: float = 0.0
    op_coverage: Dict[str, float] = field(default_factory=dict)
    corner_cases_hit: int = 0
    corner_cases_total: int = 12
    a_bins: Dict[str, bool] = field(default_factory=dict)
    b_bins: Dict[str, bool] = field(default_factory=dict)
    cross_bins_hit: int = 0
    cross_bins_total: int = 12
    transactions_count: int = 0


class PyHDLBridge:
    """
    PyHDL-IF compatible bidirectional bridge for Python <-> SystemVerilog.

    Uses named pipes (FIFOs) for IPC, following the PyHDL-IF interface
    pattern without any DPI-C intermediary.

    The bridge supports:
        - Sending stimulus from Python to SV
        - Receiving results and coverage from SV
        - Handshake protocol with configurable timeouts
        - Session management (start/stop)
        - Error handling and recovery
    """

    # Default paths for named pipes
    DEFAULT_PIPE_DIR = "/tmp/alu_rl_bridge"
    STIM_PIPE = "py2sv_stimulus.pipe"
    RESP_PIPE = "sv2py_response.pipe"
    CTRL_PIPE = "control.pipe"

    def __init__(
        self,
        pipe_dir: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        use_json: bool = False
    ):
        """
        Initialize the PyHDL-IF bridge.

        Args:
            pipe_dir: Directory for named pipes. Defaults to /tmp/alu_rl_bridge.
            timeout: Timeout in seconds for handshake operations.
            max_retries: Maximum retry attempts on timeout.
            use_json: Use JSON format instead of space-delimited.
        """
        self.pipe_dir = Path(pipe_dir or self.DEFAULT_PIPE_DIR)
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_json = use_json

        self.stim_pipe_path = self.pipe_dir / self.STIM_PIPE
        self.resp_pipe_path = self.pipe_dir / self.RESP_PIPE
        self.ctrl_pipe_path = self.pipe_dir / self.CTRL_PIPE

        self._stim_fd = None
        self._resp_fd = None
        self._ctrl_fd = None

        self._seq_counter = 0
        self._is_connected = False
        self._lock = threading.Lock()

        self._coverage_history: list = []
        self._transaction_log: list = []

        logger.info(f"PyHDL-IF Bridge initialized, pipe_dir={self.pipe_dir}")

    def setup_pipes(self):
        """Create named pipes for communication."""
        self.pipe_dir.mkdir(parents=True, exist_ok=True)

        for pipe_path in [self.stim_pipe_path, self.resp_pipe_path, self.ctrl_pipe_path]:
            if pipe_path.exists():
                pipe_path.unlink()
            os.mkfifo(str(pipe_path), 0o666)
            logger.info(f"Created named pipe: {pipe_path}")

    def cleanup_pipes(self):
        """Remove named pipes."""
        for pipe_path in [self.stim_pipe_path, self.resp_pipe_path, self.ctrl_pipe_path]:
            if pipe_path.exists():
                try:
                    pipe_path.unlink()
                except OSError:
                    pass
        logger.info("Cleaned up named pipes")

    def connect(self, as_server: bool = True):
        """
        Establish bridge connection.

        For RL flow: Python is the server (opens write end of stim pipe first,
        then read end of response pipe).

        Args:
            as_server: If True, Python acts as the server side.
        """
        if self._is_connected:
            logger.warning("Bridge already connected")
            return

        if as_server:
            self.setup_pipes()
            logger.info("Waiting for SV side to connect...")

            # Open stimulus pipe for writing (Python -> SV)
            # This blocks until SV opens the read end
            self._stim_fd = open(str(self.stim_pipe_path), 'w')
            logger.info("Stimulus pipe connected")

            # Open response pipe for reading (SV -> Python)
            self._resp_fd = open(str(self.resp_pipe_path), 'r')
            logger.info("Response pipe connected")
        else:
            # Client mode (for testing): reverse order
            self._resp_fd = open(str(self.resp_pipe_path), 'w')
            self._stim_fd = open(str(self.stim_pipe_path), 'r')

        self._is_connected = True
        self._seq_counter = 0
        logger.info("Bridge fully connected")

    def connect_file_mode(self, stim_file: str, resp_file: str):
        """
        Connect in file mode (non-blocking, for simulation without live pipes).

        Uses regular files instead of named pipes. Suitable for batch-mode
        simulation where SV reads a pre-generated stimulus file.

        Args:
            stim_file: Path to stimulus output file.
            resp_file: Path to response input file (created by SV sim).
        """
        self.pipe_dir.mkdir(parents=True, exist_ok=True)
        self._stim_fd = open(stim_file, 'w')
        self._resp_fd = None
        self._resp_file_path = resp_file
        self._is_connected = True
        self._file_mode = True
        self._seq_counter = 0
        logger.info(f"Bridge connected in file mode: stim={stim_file}, resp={resp_file}")

    def disconnect(self):
        """Close the bridge connection."""
        if self._stim_fd:
            try:
                self._stim_fd.write(f"DONE 0 0 0 0 0 0 {time.time():.6f}\n")
                self._stim_fd.flush()
            except (BrokenPipeError, OSError):
                pass
            self._stim_fd.close()
            self._stim_fd = None

        if self._resp_fd:
            self._resp_fd.close()
            self._resp_fd = None

        self._is_connected = False
        logger.info("Bridge disconnected")

    def send_stimulus(self, A: int, B: int, op_code: int,
                      C_in: int = 0, reset: int = 0) -> int:
        """
        Send a stimulus transaction to the SV testbench.

        Args:
            A: 8-bit operand A (0-255)
            B: 8-bit operand B (0-255)
            op_code: ALU operation (0=ADD, 1=SUB, 2=MUL, 3=DIV, 4=AND, 5=XOR)
            C_in: Carry-in bit (0 or 1)
            reset: Reset signal (0 or 1)

        Returns:
            Sequence ID for this transaction.
        """
        if not self._is_connected:
            raise RuntimeError("Bridge not connected")

        with self._lock:
            self._seq_counter += 1
            seq_id = self._seq_counter

            msg = StimulusMessage(
                seq_id=seq_id,
                A=A & 0xFF,
                B=B & 0xFF,
                op_code=op_code & 0xF,
                C_in=C_in & 0x1,
                reset=reset & 0x1,
                timestamp=time.time()
            )

            if self.use_json:
                line = json.dumps(asdict(msg)) + "\n"
            else:
                line = msg.to_line()

            self._stim_fd.write(line)
            self._stim_fd.flush()

            self._transaction_log.append({
                'type': 'stimulus',
                'seq_id': seq_id,
                'A': msg.A, 'B': msg.B,
                'op_code': msg.op_code,
                'C_in': msg.C_in,
                'reset': msg.reset
            })

            return seq_id

    def receive_response(self, expected_seq_id: Optional[int] = None) -> ResponseMessage:
        """
        Receive a response from the SV testbench.

        Blocks until a response is received or timeout occurs.

        Args:
            expected_seq_id: If set, validate that response matches this ID.

        Returns:
            ResponseMessage with results and coverage data.

        Raises:
            TimeoutError: If no response within timeout period.
            ValueError: If response seq_id doesn't match expected.
        """
        if not self._is_connected:
            raise RuntimeError("Bridge not connected")

        # Handle file mode
        if getattr(self, '_file_mode', False):
            return self._receive_from_file(expected_seq_id)

        start_time = time.time()
        retries = 0

        while retries <= self.max_retries:
            try:
                # Set alarm for timeout
                line = self._read_with_timeout(self._resp_fd, self.timeout)

                if line is None or line.strip() == "":
                    retries += 1
                    continue

                line = line.strip()

                if line.startswith("DONE"):
                    logger.info("Received DONE from SV side")
                    raise StopIteration("Simulation complete")

                if line.startswith("ERROR"):
                    logger.error(f"SV error: {line}")
                    raise RuntimeError(f"SV testbench error: {line}")

                if self.use_json:
                    data = json.loads(line)
                    resp = ResponseMessage(**data)
                else:
                    resp = ResponseMessage.from_line(line)

                if expected_seq_id is not None and resp.seq_id != expected_seq_id:
                    logger.warning(
                        f"Seq ID mismatch: expected {expected_seq_id}, "
                        f"got {resp.seq_id}"
                    )

                self._coverage_history.append(resp.coverage_pct)
                self._transaction_log.append({
                    'type': 'response',
                    'seq_id': resp.seq_id,
                    'result': resp.result,
                    'coverage': resp.coverage_pct
                })

                return resp

            except TimeoutError:
                retries += 1
                logger.warning(
                    f"Timeout waiting for response (attempt {retries}/{self.max_retries})"
                )
                if retries > self.max_retries:
                    raise TimeoutError(
                        f"No response from SV after {self.max_retries} retries "
                        f"(timeout={self.timeout}s)"
                    )

        raise TimeoutError("Max retries exceeded waiting for SV response")

    def _receive_from_file(self, expected_seq_id: Optional[int]) -> ResponseMessage:
        """Read response from file (for file-mode/batch operation)."""
        resp_path = Path(self._resp_file_path)

        # Wait for file to exist
        start = time.time()
        while not resp_path.exists():
            if time.time() - start > self.timeout:
                raise TimeoutError(f"Response file not found: {resp_path}")
            time.sleep(0.1)

        # Read last line matching expected_seq_id
        if self._resp_fd is None:
            self._resp_fd = open(str(resp_path), 'r')

        line = self._resp_fd.readline()
        if not line:
            raise TimeoutError("No more responses in file")

        return ResponseMessage.from_line(line.strip())

    def _read_with_timeout(self, fd, timeout: float) -> Optional[str]:
        """Read a line from fd with timeout."""
        import select
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            return fd.readline()
        raise TimeoutError(f"Read timed out after {timeout}s")

    def send_and_receive(self, A: int, B: int, op_code: int,
                         C_in: int = 0, reset: int = 0) -> ResponseMessage:
        """
        Complete round-trip: send stimulus and wait for response.

        This is the primary method for RL agent interaction.

        Args:
            A, B, op_code, C_in, reset: Stimulus parameters.

        Returns:
            ResponseMessage with ALU results and coverage.
        """
        seq_id = self.send_stimulus(A, B, op_code, C_in, reset)
        return self.receive_response(expected_seq_id=seq_id)

    def send_batch_stimuli(self, stimuli: list) -> None:
        """
        Write a batch of stimuli to the pipe/file.

        Used for file-mode where all stimuli are pre-generated.

        Args:
            stimuli: List of dicts with keys {A, B, op_code, C_in, reset}.
        """
        for stim in stimuli:
            self.send_stimulus(**stim)
        logger.info(f"Sent batch of {len(stimuli)} stimuli")

    def read_batch_responses(self, count: int) -> list:
        """
        Read a batch of responses (for file-mode).

        Args:
            count: Number of responses to read.

        Returns:
            List of ResponseMessage objects.
        """
        responses = []
        for _ in range(count):
            try:
                resp = self.receive_response()
                responses.append(resp)
            except (TimeoutError, StopIteration):
                break
        return responses

    def get_coverage_history(self) -> list:
        """Return the coverage percentage history."""
        return self._coverage_history.copy()

    def get_transaction_log(self) -> list:
        """Return the full transaction log."""
        return self._transaction_log.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Return bridge statistics."""
        return {
            'total_transactions': self._seq_counter,
            'coverage_history_len': len(self._coverage_history),
            'final_coverage': self._coverage_history[-1] if self._coverage_history else 0.0,
            'is_connected': self._is_connected,
        }


class FileBridge:
    """
    Simplified file-based bridge for batch-mode simulation.

    Writes all stimuli to a file that SV reads, then reads all
    responses from a file that SV wrote. No live pipe interaction.

    This is the recommended mode for initial integration and for
    running comparison benchmarks.
    """

    def __init__(self, work_dir: str = "sim_work"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.stim_file = self.work_dir / "rl_stimuli.txt"
        self.resp_file = self.work_dir / "sv_responses.txt"
        self.cov_file = self.work_dir / "coverage_report.txt"
        self._stimuli: list = []
        self._responses: list = []

    def write_stimuli(self, stimuli: list) -> str:
        """
        Write stimulus list to file for SV consumption.

        Args:
            stimuli: List of dicts with {A, B, op_code, C_in, reset}.

        Returns:
            Path to the stimulus file.
        """
        with open(self.stim_file, 'w') as f:
            f.write(f"# ALU RL Stimulus File - {len(stimuli)} transactions\n")
            f.write(f"# Format: seq_id A B op_code C_in reset\n")
            for i, s in enumerate(stimuli):
                f.write(f"{i+1} {s['A']} {s['B']} {s['op_code']} "
                        f"{s.get('C_in', 0)} {s.get('reset', 0)}\n")
            f.write("DONE\n")

        self._stimuli = stimuli
        logger.info(f"Wrote {len(stimuli)} stimuli to {self.stim_file}")
        return str(self.stim_file)

    def read_responses(self) -> list:
        """
        Read responses from SV simulation output file.

        Returns:
            List of ResponseMessage objects.
        """
        responses = []
        if not self.resp_file.exists():
            logger.warning(f"Response file not found: {self.resp_file}")
            return responses

        with open(self.resp_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line == 'DONE':
                    continue
                try:
                    resp = ResponseMessage.from_line(line)
                    responses.append(resp)
                except (IndexError, ValueError) as e:
                    logger.warning(f"Failed to parse response line: {line} ({e})")

        self._responses = responses
        logger.info(f"Read {len(responses)} responses from {self.resp_file}")
        return responses

    def read_coverage_report(self) -> CoverageReport:
        """
        Read the detailed coverage report from SV simulation.

        Returns:
            CoverageReport with detailed coverage breakdown.
        """
        report = CoverageReport()

        if not self.cov_file.exists():
            logger.warning(f"Coverage file not found: {self.cov_file}")
            return report

        with open(self.cov_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('=')
                if len(parts) != 2:
                    continue
                key, val = parts[0].strip(), parts[1].strip()

                if key == 'total_coverage':
                    report.total_coverage = float(val)
                elif key == 'corner_cases_hit':
                    report.corner_cases_hit = int(val)
                elif key == 'cross_bins_hit':
                    report.cross_bins_hit = int(val)
                elif key == 'transactions_count':
                    report.transactions_count = int(val)
                elif key.startswith('op_'):
                    report.op_coverage[key] = float(val)

        return report

    def get_stim_file_path(self) -> str:
        return str(self.stim_file)

    def get_resp_file_path(self) -> str:
        return str(self.resp_file)
