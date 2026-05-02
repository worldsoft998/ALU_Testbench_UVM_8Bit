#!/usr/bin/env python3
"""
Evaluate a trained RL agent for ALU coverage-directed verification.

Usage
-----
    python -m ai.evaluate --algorithm ppo --model results/models/ppo_model
    python -m ai.evaluate --algorithm dqn --model results/models/dqn_model --episodes 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.agents.coverage_agent import CoverageAgent, RandomBaselineAgent
from ai.core.config import RLConfig


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate AId-VO RL agent")
    p.add_argument(
        "--algorithm", "-a", default="ppo",
        choices=["ppo", "dqn", "a2c"],
    )
    p.add_argument("--model", "-m", required=True, help="Path to saved model")
    p.add_argument("--episodes", "-n", type=int, default=10)
    p.add_argument("--seed", "-s", type=int, default=42)
    p.add_argument("--target-coverage", type=float, default=95.0)
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--output-dir", "-o", default="results")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    env_kwargs = {
        "target_coverage": args.target_coverage,
        "max_steps": args.max_steps,
        "base_seed": args.seed,
    }

    rl_config = RLConfig(algorithm=args.algorithm, seed=args.seed)

    # Evaluate trained agent
    agent = CoverageAgent(
        algorithm=args.algorithm,
        env_kwargs=env_kwargs,
        rl_config=rl_config,
    )
    agent.load(args.model)

    print(f"Evaluating {args.algorithm.upper()} ({args.episodes} episodes) ...")
    ai_results = agent.evaluate(n_episodes=args.episodes)

    # Evaluate baseline
    print(f"Evaluating random baseline ({args.episodes} episodes) ...")
    baseline = RandomBaselineAgent(env_kwargs=env_kwargs, seed=args.seed)
    bl_results = baseline.evaluate(n_episodes=args.episodes)

    # Print comparison
    print("\n" + "=" * 60)
    print(f"  {'Metric':<25} {'AI':>12} {'Baseline':>12}")
    print("-" * 60)
    print(f"  {'Mean Coverage':<25} {ai_results['mean_coverage']:>11.1f}% {bl_results['mean_coverage']:>11.1f}%")
    print(f"  {'Max Coverage':<25} {ai_results['max_coverage']:>11.1f}% {bl_results['max_coverage']:>11.1f}%")
    print(f"  {'Mean Transactions':<25} {ai_results['mean_transactions']:>12,.0f} {bl_results['mean_transactions']:>12,.0f}")
    print(f"  {'Mean Steps':<25} {ai_results['mean_steps']:>12.1f} {bl_results['mean_steps']:>12.1f}")
    print("=" * 60)

    txn_reduction = 0.0
    if bl_results["mean_transactions"] > 0:
        txn_reduction = (
            1 - ai_results["mean_transactions"] / bl_results["mean_transactions"]
        ) * 100
    print(f"\n  Transaction reduction: {txn_reduction:+.1f}%")

    # Save
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"eval_{args.algorithm}_vs_baseline.json", "w") as f:
        json.dump(
            {"ai": ai_results, "baseline": bl_results, "transaction_reduction_pct": txn_reduction},
            f, indent=2, default=str,
        )
    print(f"\nResults saved to {out_dir}/eval_{args.algorithm}_vs_baseline.json")


if __name__ == "__main__":
    main()
