"""
Main AI verification orchestrator.

Coordinates the RL agent, simulator (Python model or VCS), coverage analysis,
and seed optimisation into a closed-loop verification flow.

Flow
----
1.  Optionally train an RL agent on the Python ALU model.
2.  For each verification iteration:
    a.  Agent observes current coverage state.
    b.  Agent selects an action (seed / bias / opcode focus / batch size).
    c.  Orchestrator translates action → simulation directive.
    d.  Directive is executed (Python model or VCS).
    e.  Coverage is parsed and fed back to the agent.
3.  Loop terminates when target coverage is reached or iteration budget
    is exhausted.
4.  Results are logged and a comparison report can be generated.
"""

from __future__ import annotations

import json
import time
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from ai.core.config import AIVerificationConfig
from ai.environments.alu_coverage_env import ALUCoverageEnv
from ai.environments.alu_sim_model import (
    CoverageModel,
    PythonSimRunner,
)
from ai.agents.coverage_agent import CoverageAgent, RandomBaselineAgent
from ai.generators.stimulus_generator import AIDirectedStimulusEngine, SimulationDirective
from ai.generators.seed_optimizer import SeedRecord
from ai.parsers.coverage_parser import CoverageSnapshot, UnifiedCoverageParser


class VerificationRun:
    """Container for one complete verification run's results."""

    def __init__(self, name: str, mode: str = "ai"):
        self.name = name
        self.mode = mode  # 'ai' or 'baseline'
        self.snapshots: list[CoverageSnapshot] = []
        self.directives: list[SimulationDirective] = []
        self.total_transactions = 0
        self.total_wall_time = 0.0
        self.final_coverage = 0.0
        self.iterations = 0

    def add_snapshot(self, snap: CoverageSnapshot, directive: Optional[SimulationDirective] = None):
        self.snapshots.append(snap)
        if directive:
            self.directives.append(directive)
        self.total_transactions = snap.total_transactions
        self.final_coverage = snap.coverage_pct
        self.iterations = snap.iteration

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mode": self.mode,
            "final_coverage": self.final_coverage,
            "total_transactions": self.total_transactions,
            "iterations": self.iterations,
            "total_wall_time": self.total_wall_time,
            "coverage_trace": [s.coverage_pct for s in self.snapshots],
            "transactions_trace": [s.total_transactions for s in self.snapshots],
        }


class Orchestrator:
    """
    Central verification orchestrator.

    Supports two execution modes:
        - **Python model** (default): fast, no VCS required.
        - **VCS mode**: runs Synopsys VCS simulations via shell.
    """

    def __init__(self, config: AIVerificationConfig):
        self.config = config
        self._parser = UnifiedCoverageParser()
        self._engine = AIDirectedStimulusEngine(base_seed=config.rl.seed)
        self._results_dir = Path(config.output_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_ai_verification(
        self,
        agent: Optional[CoverageAgent] = None,
        train_first: bool = True,
        model_path: Optional[str] = None,
    ) -> VerificationRun:
        """
        Execute AI-directed verification flow.

        If *train_first* is True, trains the agent before deployment.
        If *model_path* is given, loads a pre-trained model.
        """
        run = VerificationRun(
            name=f"ai_{self.config.rl.algorithm}",
            mode="ai",
        )

        env_kwargs = {
            "target_coverage": self.config.coverage.target_coverage,
            "max_steps": self.config.max_iterations,
            "base_seed": self.config.rl.seed,
            "transactions_per_step": self.config.transactions_per_iteration,
        }

        if agent is None:
            agent = CoverageAgent(
                algorithm=self.config.rl.algorithm,
                env_kwargs=env_kwargs,
                rl_config=self.config.rl,
            )

        if model_path and Path(model_path).exists():
            agent.load(model_path)
        elif train_first:
            print(f"[Orchestrator] Training {self.config.rl.algorithm.upper()} agent ...")
            summary = agent.train(
                total_timesteps=self.config.rl.total_timesteps,
                save_path=str(
                    self._results_dir / "models" / f"{self.config.rl.algorithm}_model"
                ),
            )
            print(f"[Orchestrator] Training complete: {summary}")

        # Deployment loop
        if self.config.use_python_model:
            run = self._run_python_ai(agent, run, env_kwargs)
        else:
            run = self._run_vcs_ai(agent, run)

        self._save_run(run)
        return run

    def run_baseline_verification(self) -> VerificationRun:
        """Run the baseline (non-AI) verification for comparison."""
        run = VerificationRun(name="baseline_random", mode="baseline")

        if self.config.use_python_model:
            run = self._run_python_baseline(run)
        else:
            run = self._run_vcs_baseline(run)

        self._save_run(run)
        return run

    def run_comparison(
        self,
        algorithms: Optional[list[str]] = None,
        train_timesteps: Optional[int] = None,
    ) -> dict:
        """
        Run baseline + one or more AI algorithms and return comparison data.
        """
        if algorithms is None:
            algorithms = ["ppo", "dqn", "a2c"]

        results = {}

        # Baseline
        print("[Orchestrator] Running baseline verification ...")
        baseline = self.run_baseline_verification()
        results["baseline"] = baseline.to_dict()

        # AI runs
        for algo in algorithms:
            print(f"\n[Orchestrator] Running AI verification with {algo.upper()} ...")
            self.config.rl.algorithm = algo
            if train_timesteps:
                self.config.rl.total_timesteps = train_timesteps
            ai_run = self.run_ai_verification(train_first=True)
            results[algo] = ai_run.to_dict()

        # Save comparison
        out_path = self._results_dir / "comparison.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[Orchestrator] Comparison saved to {out_path}")

        return results

    # ------------------------------------------------------------------
    # Python model execution
    # ------------------------------------------------------------------

    def _run_python_ai(
        self,
        agent: CoverageAgent,
        run: VerificationRun,
        env_kwargs: dict,
    ) -> VerificationRun:
        """Deploy trained agent against Python ALU model."""
        print("[Orchestrator] Deploying AI agent (Python model) ...")
        t0 = time.time()

        env = ALUCoverageEnv(**env_kwargs)
        obs, info = env.reset(seed=self.config.rl.seed)

        for step in range(self.config.max_iterations):
            action = agent.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)

            snap = CoverageSnapshot(
                iteration=step + 1,
                total_transactions=info.get("total_transactions", 0),
                coverage_pct=info.get("coverage_pct", 0.0),
                covered_bins=info.get("total_covered", 0),
                total_bins=CoverageModel.NUM_BINS,
                bin_vector=obs[:CoverageModel.NUM_BINS].copy(),
                bin_names=list(CoverageModel.BIN_NAMES),
                uncovered_bins=info.get("uncovered_bins", []),
                source="python",
            )
            run.add_snapshot(snap)

            print(
                f"  Step {step+1:3d} | "
                f"Cov {info.get('coverage_pct', 0):.1f}% | "
                f"Txns {info.get('total_transactions', 0):,}"
            )

            if terminated or truncated:
                break

        run.total_wall_time = time.time() - t0
        return run

    def _run_python_baseline(self, run: VerificationRun) -> VerificationRun:
        """Run baseline random verification using Python model."""
        print("[Orchestrator] Running baseline (Python model) ...")
        t0 = time.time()

        sim = PythonSimRunner()
        from ai.environments.alu_sim_model import StimulusGenerator
        gen = StimulusGenerator(seed=self.config.rl.seed)

        for step in range(self.config.max_iterations):
            gen.set_seed(self.config.rl.seed + step * 997)
            txns = gen.generate_default(n=self.config.transactions_per_iteration)
            sim.run_batch(txns)

            snap = self._parser.from_python_model(
                sim.coverage,
                iteration=step + 1,
                total_transactions=sim.total_transactions,
            )
            run.add_snapshot(snap)

            print(
                f"  Step {step+1:3d} | "
                f"Cov {snap.coverage_pct:.1f}% | "
                f"Txns {sim.total_transactions:,}"
            )

            if snap.coverage_pct >= self.config.coverage.target_coverage:
                break

        run.total_wall_time = time.time() - t0
        return run

    # ------------------------------------------------------------------
    # VCS execution
    # ------------------------------------------------------------------

    def _run_vcs_ai(
        self,
        agent: CoverageAgent,
        run: VerificationRun,
    ) -> VerificationRun:
        """Deploy agent with live VCS simulations (requires VCS licence)."""
        print("[Orchestrator] Deploying AI agent (VCS mode) ...")
        t0 = time.time()

        cumulative_cov = CoverageModel()
        env_kwargs = {
            "target_coverage": self.config.coverage.target_coverage,
            "max_steps": self.config.max_iterations,
        }
        env = ALUCoverageEnv(**env_kwargs)
        obs, _ = env.reset(seed=self.config.rl.seed)

        for step in range(self.config.max_iterations):
            action = agent.predict(obs, deterministic=True)

            # Decode action into directive
            sb, ob, of_, bs = env._decode_action(action)
            directive = SimulationDirective(
                seed=self.config.rl.seed * 1000 + step * 10 + sb,
                num_transactions=env.BATCH_SIZES[bs],
                opcode_weights=([1.0 / 6] * 6),
                operand_bias=env.OPERAND_BIAS_MAP[ob],
                iteration=step,
            )

            # Run VCS
            log_path = self._run_vcs_sim(directive, step)

            # Parse results
            if log_path and Path(log_path).exists():
                snap = self._parser.from_vcs_log(log_path, iteration=step + 1)
            else:
                snap = CoverageSnapshot(
                    iteration=step + 1,
                    total_transactions=0,
                    coverage_pct=cumulative_cov.coverage_percentage,
                    covered_bins=cumulative_cov.total_covered,
                    total_bins=CoverageModel.NUM_BINS,
                    bin_vector=cumulative_cov.covered_vector,
                    bin_names=list(CoverageModel.BIN_NAMES),
                    uncovered_bins=cumulative_cov.uncovered_bins,
                    source="vcs",
                )

            run.add_snapshot(snap, directive)

            # Update observation for next step (use env internally)
            obs, _, terminated, truncated, _ = env.step(action)

            if terminated or truncated:
                break
            if snap.coverage_pct >= self.config.coverage.target_coverage:
                break

        run.total_wall_time = time.time() - t0
        return run

    def _run_vcs_baseline(self, run: VerificationRun) -> VerificationRun:
        """Run baseline VCS simulations with random seeds."""
        print("[Orchestrator] Running baseline (VCS mode) ...")
        t0 = time.time()

        for step in range(self.config.max_iterations):
            seed = self.config.rl.seed + step * 997
            directive = SimulationDirective(
                seed=seed,
                num_transactions=self.config.transactions_per_iteration,
                iteration=step,
            )

            log_path = self._run_vcs_sim(directive, step, prefix="baseline")

            if log_path and Path(log_path).exists():
                snap = self._parser.from_vcs_log(log_path, iteration=step + 1)
            else:
                snap = CoverageSnapshot(
                    iteration=step + 1,
                    total_transactions=0,
                    coverage_pct=0.0,
                    covered_bins=0,
                    total_bins=CoverageModel.NUM_BINS,
                    bin_vector=np.zeros(CoverageModel.NUM_BINS, dtype=np.float32),
                    bin_names=list(CoverageModel.BIN_NAMES),
                    uncovered_bins=list(CoverageModel.BIN_NAMES),
                    source="vcs",
                )

            run.add_snapshot(snap, directive)

            if snap.coverage_pct >= self.config.coverage.target_coverage:
                break

        run.total_wall_time = time.time() - t0
        return run

    def _run_vcs_sim(
        self,
        directive: SimulationDirective,
        step: int,
        prefix: str = "ai",
    ) -> Optional[str]:
        """Execute one VCS simulation run. Returns log file path."""
        cfg = self.config.simulation
        log_dir = Path(cfg.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{prefix}_step{step:04d}.log"

        plusargs = directive.to_vcs_plusargs()
        cmd = [
            "bash", "scripts/run_vcs.sh",
            "--seed", str(directive.seed),
            "--log", str(log_file),
        ] + plusargs

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=cfg.timeout_ns // 1_000_000,
                cwd=str(Path.cwd()),
            )
            if result.returncode != 0:
                print(f"  [VCS] Warning: non-zero exit at step {step}")
        except FileNotFoundError:
            print(f"  [VCS] scripts/run_vcs.sh not found – skipping")
            return None
        except subprocess.TimeoutExpired:
            print(f"  [VCS] Timeout at step {step}")
            return None

        return str(log_file)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_run(self, run: VerificationRun) -> None:
        out = self._results_dir / f"{run.name}_results.json"
        with open(out, "w") as f:
            json.dump(run.to_dict(), f, indent=2)
        print(f"[Orchestrator] Results saved to {out}")
