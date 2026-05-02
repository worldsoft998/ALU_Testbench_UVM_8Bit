#!/usr/bin/env python3
"""
Train an RL agent for ALU coverage-directed verification.

Usage
-----
    python -m ai.train --algorithm ppo --timesteps 50000 --seed 42
    python -m ai.train --algorithm dqn --timesteps 30000
    python -m ai.train --algorithm a2c --timesteps 40000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai.core.config import AIVerificationConfig, RLConfig
from ai.agents.coverage_agent import CoverageAgent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train AId-VO RL agent")
    p.add_argument(
        "--algorithm", "-a", default="ppo",
        choices=["ppo", "dqn", "a2c"],
        help="RL algorithm (default: ppo)",
    )
    p.add_argument(
        "--timesteps", "-t", type=int, default=50_000,
        help="Total training timesteps (default: 50000)",
    )
    p.add_argument(
        "--seed", "-s", type=int, default=42,
        help="Random seed (default: 42)",
    )
    p.add_argument(
        "--target-coverage", type=float, default=95.0,
        help="Target coverage percentage (default: 95.0)",
    )
    p.add_argument(
        "--max-steps", type=int, default=100,
        help="Max steps per episode (default: 100)",
    )
    p.add_argument(
        "--output-dir", "-o", default="results",
        help="Output directory (default: results)",
    )
    p.add_argument(
        "--learning-rate", type=float, default=3e-4,
        help="Learning rate (default: 3e-4)",
    )
    p.add_argument(
        "--verbose", "-v", type=int, default=1,
        help="Verbosity level (default: 1)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    config = AIVerificationConfig.from_args(
        ai_enabled=True,
        algorithm=args.algorithm,
        target_coverage=args.target_coverage,
        seed=args.seed,
    )
    config.rl.learning_rate = args.learning_rate
    config.rl.verbose = args.verbose
    config.max_iterations = args.max_steps
    config.output_dir = args.output_dir

    env_kwargs = {
        "target_coverage": args.target_coverage,
        "max_steps": args.max_steps,
        "base_seed": args.seed,
    }

    agent = CoverageAgent(
        algorithm=args.algorithm,
        env_kwargs=env_kwargs,
        rl_config=config.rl,
    )

    print(f"Training {args.algorithm.upper()} for {args.timesteps} timesteps ...")
    model_path = str(Path(args.output_dir) / "models" / f"{args.algorithm}_model")
    summary = agent.train(
        total_timesteps=args.timesteps,
        save_path=model_path,
    )

    print("\n--- Training Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Save summary
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"training_summary_{args.algorithm}.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Quick evaluation
    print(f"\nEvaluating trained {args.algorithm.upper()} agent (10 episodes) ...")
    eval_results = agent.evaluate(n_episodes=10)
    print(f"  Mean coverage : {eval_results['mean_coverage']:.1f}%")
    print(f"  Mean txns     : {eval_results['mean_transactions']:,.0f}")

    with open(out_dir / f"eval_summary_{args.algorithm}.json", "w") as f:
        json.dump(eval_results, f, indent=2, default=str)

    print(f"\nModel saved to: {model_path}")
    print(f"Results saved to: {out_dir}/")


if __name__ == "__main__":
    main()
