"""
VCS simulation runner. Manages compilation and simulation execution.
Controls simulation via plusargs without modifying testbench files.
"""

import os
import time
import subprocess
import logging
import shutil
from typing import Optional
from ..core.config import AgentConfig

logger = logging.getLogger(__name__)


class VCSRunner:
    """
    Interface to Synopsys VCS simulator.
    Runs simulations with AI-selected seeds and collects coverage data.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.sim_cfg = config.simulation
        self.project_root = os.path.abspath(config.project_root)
        self.work_dir = os.path.join(self.project_root, self.sim_cfg.work_dir)
        self._compiled = False
        self._compile_binary = os.path.join(self.work_dir, "simv")

    def compile(self) -> bool:
        """Compile the design and testbench with VCS."""
        os.makedirs(self.work_dir, exist_ok=True)

        dut_files = [os.path.join(self.project_root, f) for f in self.sim_cfg.dut_files]
        tb_files = [os.path.join(self.project_root, f) for f in self.sim_cfg.tb_files]
        all_files = dut_files + tb_files

        # Check all source files exist
        for f in all_files:
            if not os.path.exists(f):
                logger.error(f"Source file not found: {f}")
                return False

        compile_cmd = self._build_compile_command(all_files)
        logger.info(f"Compiling: {' '.join(compile_cmd[:5])}...")

        try:
            result = subprocess.run(
                compile_cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            compile_log = os.path.join(self.work_dir, "compile.log")
            with open(compile_log, "w") as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n=== STDERR ===\n")
                    f.write(result.stderr)

            if result.returncode != 0:
                logger.error(f"Compilation failed. See {compile_log}")
                logger.error(result.stderr[:500] if result.stderr else "No error output")
                return False

            self._compiled = True
            logger.info("Compilation successful.")
            return True

        except FileNotFoundError:
            logger.error(
                "VCS not found. Ensure Synopsys VCS is installed and in PATH. "
                "Set VCS_HOME environment variable if needed."
            )
            return False
        except subprocess.TimeoutExpired:
            logger.error("Compilation timed out after 300s.")
            return False

    def run_simulation(self, seed: int, num_items: int = 5000,
                       iteration: int = 0, tag: str = "ai") -> dict:
        """
        Run a simulation with the given seed.

        Returns dict with:
            - log_file: path to simulation log
            - coverage_dir: path to coverage database
            - wall_time: wall clock time in seconds
            - return_code: process return code
            - num_transactions: number of transactions
        """
        iter_dir = os.path.join(
            self.work_dir, f"iter_{tag}_{iteration:04d}_seed_{seed}"
        )
        os.makedirs(iter_dir, exist_ok=True)

        log_file = os.path.join(iter_dir, "simulation.log")
        cov_dir = os.path.join(iter_dir, "coverage_db")

        run_cmd = self._build_run_command(seed, num_items, cov_dir)
        logger.debug(f"Running: {' '.join(run_cmd[:8])}...")

        start_time = time.time()
        try:
            result = subprocess.run(
                run_cmd,
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )
            wall_time = time.time() - start_time

            with open(log_file, "w") as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n=== STDERR ===\n")
                    f.write(result.stderr)

            if result.returncode != 0:
                logger.warning(
                    f"Simulation returned non-zero ({result.returncode}) "
                    f"for seed={seed}"
                )

            return {
                "log_file": log_file,
                "coverage_dir": cov_dir if os.path.isdir(cov_dir) else None,
                "wall_time": wall_time,
                "return_code": result.returncode,
                "num_transactions": num_items,
                "seed": seed,
                "iteration": iteration,
            }

        except FileNotFoundError:
            logger.error("simv binary not found. Compile first.")
            return {
                "log_file": None, "coverage_dir": None,
                "wall_time": 0, "return_code": -1,
                "num_transactions": 0, "seed": seed,
                "iteration": iteration,
            }
        except subprocess.TimeoutExpired:
            wall_time = time.time() - start_time
            logger.warning(f"Simulation timed out after {wall_time:.0f}s for seed={seed}")
            return {
                "log_file": log_file, "coverage_dir": None,
                "wall_time": wall_time, "return_code": -1,
                "num_transactions": num_items, "seed": seed,
                "iteration": iteration,
            }

    def merge_coverage(self, coverage_dirs: list, output_dir: str) -> bool:
        """Merge multiple coverage databases using URG."""
        if not coverage_dirs:
            return False

        os.makedirs(output_dir, exist_ok=True)

        merge_cmd = [
            "urg",
            "-dir", *coverage_dirs,
            "-dbname", os.path.join(output_dir, "merged_db"),
            "-report", os.path.join(output_dir, "merged_report"),
            "-format", "text",
        ]

        try:
            result = subprocess.run(
                merge_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("URG merge failed or timed out.")
            return False

    def generate_coverage_report(self, coverage_dir: str, output_dir: str) -> Optional[str]:
        """Generate text coverage report from coverage database."""
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "coverage_report.txt")

        urg_cmd = [
            "urg",
            "-dir", coverage_dir,
            "-report", output_dir,
            "-format", "text",
        ]

        try:
            result = subprocess.run(
                urg_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return report_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None

    def _build_compile_command(self, source_files: list) -> list:
        """Build VCS compile command."""
        cmd = [
            "vcs",
            "-full64",
            "-sverilog",
            "+acc",
            "-timescale=" + self.sim_cfg.timescale,
            "-ntb_opts", "uvm-" + self.sim_cfg.uvm_version,
            "-cm", "line+cond+fsm+tgl+branch+assert",
            "-cm_dir", os.path.join(self.work_dir, "compile_coverage"),
            "+incdir+" + os.path.join(self.project_root, "Testbench"),
            "+incdir+" + os.path.join(self.project_root, "DUT"),
            "-o", self._compile_binary,
            "-debug_access+all",
        ]

        if self.sim_cfg.compile_opts:
            cmd.extend(self.sim_cfg.compile_opts.split())

        cmd.extend(source_files)
        return cmd

    def _build_run_command(self, seed: int, num_items: int,
                           coverage_dir: str) -> list:
        """Build simulation run command."""
        cmd = [
            self._compile_binary,
            f"+ntb_random_seed={seed}",
            f"+UVM_TESTNAME={self.sim_cfg.tb_top}",
            "+UVM_VERBOSITY=UVM_LOW",
            f"+num_items={num_items}",
            "-cm", "line+cond+fsm+tgl+branch+assert",
            "-cm_dir", coverage_dir,
            "-cm_name", f"seed_{seed}",
        ]

        if self.sim_cfg.runtime_opts:
            cmd.extend(self.sim_cfg.runtime_opts.split())

        return cmd

    def clean(self):
        """Clean simulation work directory."""
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
            logger.info(f"Cleaned work directory: {self.work_dir}")
