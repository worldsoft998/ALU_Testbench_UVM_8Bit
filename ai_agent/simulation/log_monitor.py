"""
Real-time simulation log monitor.
Watches VCS output for coverage events, errors, and progress indicators.
"""

import re
import os
import time
import logging
import threading
from typing import Optional, Callable
from ..core.config import AgentConfig

logger = logging.getLogger(__name__)


class LogEvent:
    """A parsed event from the simulation log."""
    def __init__(self, event_type: str, message: str, timestamp: float = 0):
        self.event_type = event_type  # "error", "warning", "coverage", "info", "pass", "fail"
        self.message = message
        self.timestamp = timestamp

    def __repr__(self):
        return f"LogEvent({self.event_type}: {self.message[:60]})"


class LogMonitor:
    """
    Monitor simulation logs in real-time.
    Can run in a separate thread for concurrent monitoring during simulation.
    """

    # Regex patterns for VCS/UVM log parsing
    PATTERNS = {
        "uvm_error": re.compile(r"UVM_ERROR[\s:]+(.+)"),
        "uvm_warning": re.compile(r"UVM_WARNING\s+(.+)"),
        "uvm_fatal": re.compile(r"UVM_FATAL\s+(.+)"),
        "uvm_info": re.compile(r"UVM_INFO\s+(.+)"),
        "pass": re.compile(r"pass successfully"),
        "fail": re.compile(r"error,reset=.*"),
        "coverage": re.compile(r"Coverage\s*=\s*([\d.]+)"),
        "finish": re.compile(r"\$finish"),
        "seed": re.compile(r"random_seed\s*=\s*(\d+)"),
        "sim_time": re.compile(r"Simulation\s+time:\s*([\d.]+)\s*(\w+)"),
    }

    def __init__(self, config: AgentConfig):
        self.config = config
        self._events: list = []
        self._callbacks: list = []
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None

    def register_callback(self, callback: Callable):
        """Register a callback to be called for each log event."""
        self._callbacks.append(callback)

    def parse_log_file(self, log_path: str) -> list:
        """Parse a completed log file and return events."""
        events = []
        if not os.path.exists(log_path):
            return events

        with open(log_path, "r") as f:
            for line_no, line in enumerate(f, 1):
                event = self._parse_line(line.strip(), line_no)
                if event:
                    events.append(event)

        self._events.extend(events)
        return events

    def start_monitoring(self, log_path: str):
        """Start monitoring a log file in a background thread."""
        self._monitoring = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(log_path,),
            daemon=True,
        )
        self._thread.start()
        logger.debug(f"Started monitoring: {log_path}")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def get_summary(self) -> dict:
        """Get summary of observed events."""
        summary = {
            "total_events": len(self._events),
            "errors": 0,
            "warnings": 0,
            "passes": 0,
            "fails": 0,
            "coverage_updates": [],
        }
        for e in self._events:
            if e.event_type == "uvm_error":
                summary["errors"] += 1
            elif e.event_type == "uvm_warning":
                summary["warnings"] += 1
            elif e.event_type == "pass":
                summary["passes"] += 1
            elif e.event_type == "fail":
                summary["fails"] += 1
            elif e.event_type == "coverage":
                summary["coverage_updates"].append(e.message)
        return summary

    def _parse_line(self, line: str, line_no: int = 0) -> Optional[LogEvent]:
        """Parse a single log line into an event."""
        for event_type, pattern in self.PATTERNS.items():
            match = pattern.search(line)
            if match:
                message = match.group(0)
                return LogEvent(
                    event_type=event_type,
                    message=message,
                    timestamp=line_no,
                )
        return None

    def _monitor_loop(self, log_path: str):
        """Background monitoring loop using tail-follow semantics."""
        while self._monitoring and not os.path.exists(log_path):
            time.sleep(0.5)

        if not self._monitoring:
            return

        with open(log_path, "r") as f:
            line_no = 0
            while self._monitoring:
                line = f.readline()
                if line:
                    line_no += 1
                    event = self._parse_line(line.strip(), line_no)
                    if event:
                        self._events.append(event)
                        for cb in self._callbacks:
                            try:
                                cb(event)
                            except Exception as e:
                                logger.warning(f"Callback error: {e}")
                else:
                    time.sleep(0.1)

    def clear(self):
        """Clear recorded events."""
        self._events.clear()
