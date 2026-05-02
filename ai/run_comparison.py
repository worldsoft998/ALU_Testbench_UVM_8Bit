#!/usr/bin/env python3
"""
Run a full AI vs Baseline comparison across multiple RL algorithms.

Usage
-----
    python -m ai.run_comparison
    python -m ai.run_comparison --algorithms ppo dqn a2c --timesteps 30000
    python -m ai.run_comparison --target-coverage 100 --max-iterations 200
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.core.config import AIVerificationConfig
from ai.core.orchestrator import Orchestrator
from ai.analysis.comparator import VerificationComparator
from ai.analysis.reporter import ReportGenerator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AId-VO full comparison: AI vs Baseline verification"
    )
    p.add_argument(
        "--algorithms", "-a", nargs="+", default=["ppo", "dqn", "a2c"],
        choices=["ppo", "dqn", "a2c"],
        help="RL algorithms to compare (default: ppo dqn a2c)",
    )
    p.add_argument("--timesteps", "-t", type=int, default=50_000)
    p.add_argument("--seed", "-s", type=int, default=42)
    p.add_argument("--target-coverage", type=float, default=95.0)
    p.add_argument("--max-iterations", type=int, default=50)
    p.add_argument("--transactions-per-iter", type=int, default=1000)
    p.add_argument("--output-dir", "-o", default="results")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    config = AIVerificationConfig.from_args(
        ai_enabled=True,
        algorithm=args.algorithms[0],
        target_coverage=args.target_coverage,
        seed=args.seed,
    )
    config.max_iterations = args.max_iterations
    config.transactions_per_iteration = args.transactions_per_iter
    config.output_dir = args.output_dir
    config.rl.total_timesteps = args.timesteps

    orchestrator = Orchestrator(config)

    print("=" * 70)
    print("  AId-VO — AI-Directed Verification Optimization")
    print("  Full Comparison Run")
    print("=" * 70)
    print(f"  Algorithms        : {', '.join(a.upper() for a in args.algorithms)}")
    print(f"  Training steps    : {args.timesteps:,}")
    print(f"  Target coverage   : {args.target_coverage}%")
    print(f"  Max iterations    : {args.max_iterations}")
    print(f"  Txns per iteration: {args.transactions_per_iter:,}")
    print("=" * 70)

    results = orchestrator.run_comparison(
        algorithms=args.algorithms,
        train_timesteps=args.timesteps,
    )

    # Generate comparison report
    comparator = VerificationComparator()
    text_report = comparator.generate_text_report(
        results,
        output_path=Path(args.output_dir) / "comparison_report.txt",
    )
    print(text_report)

    # Generate markdown report
    reporter = ReportGenerator(output_dir=args.output_dir)
    reporter.generate_full_report(results)
    print(f"\nMarkdown report: {args.output_dir}/report.md")
    print(f"Comparison data: {args.output_dir}/comparison.json")


if __name__ == "__main__":
    main()
