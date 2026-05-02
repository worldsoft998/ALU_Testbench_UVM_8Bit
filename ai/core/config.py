"""
Configuration management for AId-VO verification optimization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class SimulationConfig:
    """VCS simulation parameters."""
    sim_tool: str = "vcs"
    top_module: str = "Top"
    uvm_test: str = "ALU_Test"
    num_items: int = 5000
    verbosity: str = "UVM_LOW"
    timescale: str = "1ns/1ps"
    coverage_metrics: str = "line+cond+fsm+branch+tgl"
    timeout_ns: int = 10_000_000
    dut_dir: str = "DUT"
    tb_dir: str = "Testbench"
    work_dir: str = "work"
    coverage_dir: str = "coverage"
    log_dir: str = "logs"


@dataclass
class RLConfig:
    """Reinforcement learning hyperparameters."""
    algorithm: str = "ppo"
    learning_rate: float = 3e-4
    gamma: float = 0.99
    n_steps: int = 128
    batch_size: int = 64
    n_epochs: int = 10
    total_timesteps: int = 50_000
    seed: int = 42
    device: str = "auto"
    policy: str = "MlpPolicy"
    verbose: int = 1
    # DQN-specific
    buffer_size: int = 10_000
    exploration_fraction: float = 0.3
    exploration_final_eps: float = 0.05
    target_update_interval: int = 500


@dataclass
class CoverageConfig:
    """Coverage model configuration matching the UVM testbench."""
    target_coverage: float = 95.0
    a_bins: list[str] = field(default_factory=lambda: ["All_Ones", "All_Zeros", "random_stimulus"])
    b_bins: list[str] = field(default_factory=lambda: ["All_Ones", "All_Zeros", "random_stimulus"])
    opcode_bins: list[str] = field(
        default_factory=lambda: ["add", "sub", "mul", "div", "anding", "xoring"]
    )
    c_in_bins: list[int] = field(default_factory=lambda: [0, 1])
    reset_bins: list[int] = field(default_factory=lambda: [0, 1])
    corner_case_ops: list[str] = field(
        default_factory=lambda: ["Add", "Sub", "Mul", "Div", "And", "Xor"]
    )

    @property
    def num_bins(self) -> int:
        n_a = len(self.a_bins)
        n_b = len(self.b_bins)
        n_op = len(self.opcode_bins)
        n_cin = len(self.c_in_bins)
        n_rst = len(self.reset_bins)
        n_corner = len(self.corner_case_ops) * 2  # cross1 and cross2 per op
        return n_a + n_b + n_op + n_cin + n_rst + n_corner


@dataclass
class AIVerificationConfig:
    """Top-level configuration for AI-directed verification."""
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    rl: RLConfig = field(default_factory=RLConfig)
    coverage: CoverageConfig = field(default_factory=CoverageConfig)
    max_iterations: int = 50
    transactions_per_iteration: int = 1000
    use_python_model: bool = True
    enable_ai: bool = True
    output_dir: str = "results"
    model_save_dir: str = "models"

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "AIVerificationConfig":
        with open(path) as f:
            data = json.load(f)
        sim = SimulationConfig(**data.pop("simulation", {}))
        rl = RLConfig(**data.pop("rl", {}))
        cov = CoverageConfig(**data.pop("coverage", {}))
        return cls(simulation=sim, rl=rl, coverage=cov, **data)

    @classmethod
    def from_args(
        cls,
        ai_enabled: bool = True,
        algorithm: str = "ppo",
        num_items: int = 5000,
        max_iterations: int = 50,
        target_coverage: float = 95.0,
        use_python_model: bool = True,
        seed: int = 42,
    ) -> "AIVerificationConfig":
        cfg = cls()
        cfg.enable_ai = ai_enabled
        cfg.rl.algorithm = algorithm
        cfg.simulation.num_items = num_items
        cfg.max_iterations = max_iterations
        cfg.coverage.target_coverage = target_coverage
        cfg.use_python_model = use_python_model
        cfg.rl.seed = seed
        return cfg
