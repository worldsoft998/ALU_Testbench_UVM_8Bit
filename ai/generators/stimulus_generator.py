"""
High-level stimulus generation interface that bridges the RL agent's actions
into concrete simulation parameters for VCS or the Python model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ai.environments.alu_sim_model import (
    ALUTransaction,
    CoverageModel,
    StimulusGenerator as BaseStimulusGenerator,
)
from ai.generators.seed_optimizer import SeedOptimizer


@dataclass
class SimulationDirective:
    """
    A concrete set of simulation parameters to be passed to VCS or the
    Python model for one verification iteration.
    """
    seed: int = 42
    num_transactions: int = 1000
    opcode_weights: list[float] = None
    operand_bias: str = "default"
    iteration: int = 0

    def __post_init__(self):
        if self.opcode_weights is None:
            self.opcode_weights = [1.0 / 6] * 6

    def to_vcs_plusargs(self) -> list[str]:
        """Generate VCS plusarg strings for this directive."""
        args = [
            f"+ntb_random_seed={self.seed}",
        ]
        # Opcode weights encoded as plusargs for potential SV $value$plusargs use
        for i, w in enumerate(self.opcode_weights):
            args.append(f"+AI_OP_WEIGHT_{i}={w:.4f}")
        args.append(f"+AI_OPERAND_BIAS={self.operand_bias}")
        args.append(f"+AI_ITERATION={self.iteration}")
        return args

    def to_seed_file(self, path: str) -> None:
        """Write a seed file consumable by VCS."""
        with open(path, "w") as f:
            f.write(f"{self.seed}\n")


class AIDirectedStimulusEngine:
    """
    Translates RL agent decisions into simulation directives and generates
    transactions for the Python model path.

    This is the central coupling point between the AI agent and the
    simulation infrastructure.
    """

    def __init__(self, base_seed: int = 42):
        self.base_seed = base_seed
        self.seed_optimizer = SeedOptimizer(base_seed)
        self._base_gen = BaseStimulusGenerator(seed=base_seed)
        self.iteration = 0

    def create_directive_from_action(
        self,
        action: dict,
        coverage: CoverageModel,
    ) -> SimulationDirective:
        """
        Convert an RL action dictionary into a ``SimulationDirective``.

        Expected action keys:
            seed_bucket  : int  (0-9)
            operand_bias : str  ('default'|'zeros'|'ones'|'boundary'|'uniform')
            opcode_focus : int  (0=uniform, 1-6=emphasise specific op)
            batch_size   : int
        """
        seed_bucket = action.get("seed_bucket", 0)
        suggested = self.seed_optimizer.suggest_seeds(1, coverage, strategy="auto")
        seed = suggested[0] + seed_bucket * 1_000_000

        opcode_focus = action.get("opcode_focus", 0)
        if opcode_focus == 0:
            opcode_weights = self.seed_optimizer.suggest_opcode_weights(coverage)
        else:
            opcode_weights = [0.5] * 6
            opcode_weights[opcode_focus - 1] = 5.0
            total = sum(opcode_weights)
            opcode_weights = [w / total for w in opcode_weights]

        bias = action.get("operand_bias", "default")
        if bias == "auto":
            bias = self.seed_optimizer.suggest_operand_bias(coverage)

        directive = SimulationDirective(
            seed=seed,
            num_transactions=action.get("batch_size", 1000),
            opcode_weights=opcode_weights,
            operand_bias=bias,
            iteration=self.iteration,
        )
        self.iteration += 1
        return directive

    def create_baseline_directive(
        self,
        seed: Optional[int] = None,
        num_transactions: int = 1000,
    ) -> SimulationDirective:
        """Create a directive using default UVM randomisation (no AI bias)."""
        if seed is None:
            seed = int(np.random.randint(0, 2**31))
        return SimulationDirective(
            seed=seed,
            num_transactions=num_transactions,
            opcode_weights=[1.0 / 6] * 6,
            operand_bias="default",
            iteration=self.iteration,
        )

    def generate_transactions(
        self,
        directive: SimulationDirective,
    ) -> list[ALUTransaction]:
        """Generate transactions in Python according to a directive."""
        self._base_gen.set_seed(directive.seed)
        return self._base_gen.generate_biased(
            n=directive.num_transactions,
            opcode_weights=directive.opcode_weights,
            operand_bias=directive.operand_bias,
        )
