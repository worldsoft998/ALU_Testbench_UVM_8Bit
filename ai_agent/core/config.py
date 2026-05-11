"""
Configuration management for the AIa-VO framework.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SimulationConfig:
    """VCS simulation parameters."""
    simulator: str = "vcs"
    uvm_version: str = "1.2"
    timescale: str = "1ns/1ps"
    default_num_items: int = 5000
    max_num_items: int = 80000
    timeout_ns: int = 10_000_000
    compile_opts: str = ""
    runtime_opts: str = ""
    coverage_dir: str = "coverage_db"
    work_dir: str = "sim_work"
    dut_files: list = field(default_factory=lambda: [
        "DUT/ALU_DUT.sv",
        "DUT/ALU_interface.sv",
    ])
    tb_files: list = field(default_factory=lambda: [
        "Testbench/ALU_pkg.sv",
        "Testbench/ALU_Top.sv",
    ])
    tb_top: str = "Top"


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "openai"  # openai, gemini, claude
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 1024
    temperature: float = 0.3
    max_retries: int = 3
    timeout: int = 30


@dataclass
class MLConfig:
    """ML/RL model parameters."""
    algorithm: str = "bayesian"  # bayesian, rl, random_forest, ensemble
    rl_learning_rate: float = 0.01
    rl_discount_factor: float = 0.95
    rl_epsilon: float = 0.2
    rl_epsilon_decay: float = 0.995
    rl_min_epsilon: float = 0.01
    bayesian_n_initial: int = 5
    bayesian_acquisition: str = "ei"  # ei, ucb, pi
    bayesian_xi: float = 0.01
    bayesian_kappa: float = 2.576
    seed_range_min: int = 1
    seed_range_max: int = 100000
    feature_dim: int = 32


@dataclass
class AgentConfig:
    """Top-level configuration for the AI verification agent."""
    project_root: str = "."
    target_coverage: float = 100.0
    max_iterations: int = 50
    convergence_threshold: float = 0.1
    convergence_patience: int = 5
    min_runs_before_ai: int = 3
    parallel_sims: int = 1
    enable_llm: bool = True
    enable_ml: bool = True
    comparison_mode: bool = True
    baseline_seeds: list = field(default_factory=lambda: [
        12345, 54321, 98765, 11111, 22222,
        33333, 44444, 55555, 66666, 77777,
    ])
    results_dir: str = "results"
    log_level: str = "INFO"

    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ml: MLConfig = field(default_factory=MLConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "AgentConfig":
        sim_data = data.pop("simulation", {})
        llm_data = data.pop("llm", {})
        ml_data = data.pop("ml", {})
        config = cls(**data)
        if sim_data:
            config.simulation = SimulationConfig(**sim_data)
        if llm_data:
            config.llm = LLMConfig(**llm_data)
        if ml_data:
            config.ml = MLConfig(**ml_data)
        return config

    def to_dict(self) -> dict:
        """Serialize configuration to dictionary."""
        from dataclasses import asdict
        return asdict(self)

    def validate(self) -> list:
        """Validate configuration, returning list of warnings."""
        warnings = []
        if self.target_coverage > 100.0:
            warnings.append("target_coverage > 100%, clamping to 100%")
            self.target_coverage = 100.0
        if self.enable_llm:
            key = os.environ.get(self.llm.api_key_env, "")
            if not key:
                warnings.append(
                    f"LLM enabled but {self.llm.api_key_env} not set. "
                    "LLM features will be disabled at runtime."
                )
        if self.max_iterations < 1:
            warnings.append("max_iterations < 1, setting to 1")
            self.max_iterations = 1
        return warnings
