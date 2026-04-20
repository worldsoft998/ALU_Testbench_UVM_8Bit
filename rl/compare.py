#!/usr/bin/env python3
"""
RL vs Random Comparison Framework
====================================
Compares RL-guided stimulus generation against random/constrained-random
baselines for ALU verification coverage closure.

Produces:
    - Coverage trajectory plots
    - Transaction efficiency comparison
    - Statistical summary table
    - JSON results file

Usage:
    python -m rl.compare --algorithm PPO --timesteps 50000 --episodes 10
"""

import argparse
import json
import logging
import time
import os
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def run_random_baseline(
    num_transactions: int,
    num_episodes: int,
    seed: int = 42,
    weighted: bool = True,
) -> Dict[str, Any]:
    """Run random baseline and collect coverage metrics."""
    from .rl_agent import RandomBaselineAgent

    results = {
        'coverage_trajectories': [],
        'transactions_to_full_coverage': [],
        'final_coverages': [],
        'wall_times': [],
    }

    for ep in range(num_episodes):
        agent = RandomBaselineAgent(seed=seed + ep)
        start = time.time()
        ep_results = agent.run_coverage_analysis(num_transactions)
        wall_time = time.time() - start

        results['coverage_trajectories'].append(ep_results['coverage_trajectory'])
        results['final_coverages'].append(ep_results['final_coverage'])
        results['wall_times'].append(wall_time)

        # Check if full coverage was reached
        traj = ep_results['coverage_trajectory']
        full_cov_idx = next(
            (i for i, c in enumerate(traj) if c >= 100.0), None
        )
        if full_cov_idx is not None:
            results['transactions_to_full_coverage'].append(full_cov_idx + 1)
        else:
            results['transactions_to_full_coverage'].append(num_transactions)

        logger.info(
            f"Random episode {ep+1}/{num_episodes}: "
            f"coverage={ep_results['final_coverage']:.1f}%, "
            f"transactions={ep_results['transactions_used']}, "
            f"time={wall_time:.2f}s"
        )

    return results


def run_rl_agent(
    algorithm: str,
    num_transactions: int,
    num_episodes: int,
    training_timesteps: int,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train RL agent and collect coverage metrics."""
    from .rl_agent import RLVerificationAgent
    from .alu_gym_env import ALUVerifEnv

    # Train agent
    logger.info(f"Training {algorithm} agent for {training_timesteps} timesteps...")
    agent = RLVerificationAgent(
        algorithm=algorithm,
        max_transactions=num_transactions,
        target_coverage=100.0,
        n_envs=1,
        model_dir='models',
        log_dir='logs',
        seed=seed,
    )

    train_start = time.time()
    train_results = agent.train(total_timesteps=training_timesteps)
    training_time = time.time() - train_start

    results = {
        'coverage_trajectories': [],
        'transactions_to_full_coverage': [],
        'final_coverages': [],
        'wall_times': [],
        'training_time': training_time,
        'training_results': {
            k: v for k, v in train_results.items()
            if k != 'coverage_history'
        },
    }

    # Run inference episodes
    for ep in range(num_episodes):
        env = ALUVerifEnv(
            max_transactions=num_transactions,
            target_coverage=100.0,
            offline_mode=True,
        )

        obs, info = env.reset(seed=seed + ep)
        trajectory = []
        start = time.time()

        for _ in range(num_transactions):
            action, _ = agent.model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            trajectory.append(info['coverage'])
            if terminated:
                break

        wall_time = time.time() - start

        results['coverage_trajectories'].append(trajectory)
        results['final_coverages'].append(trajectory[-1] if trajectory else 0.0)
        results['wall_times'].append(wall_time)

        full_cov_idx = next(
            (i for i, c in enumerate(trajectory) if c >= 100.0), None
        )
        if full_cov_idx is not None:
            results['transactions_to_full_coverage'].append(full_cov_idx + 1)
        else:
            results['transactions_to_full_coverage'].append(num_transactions)

        logger.info(
            f"RL episode {ep+1}/{num_episodes}: "
            f"coverage={trajectory[-1]:.1f}%, "
            f"transactions={len(trajectory)}, "
            f"time={wall_time:.4f}s"
        )

    agent.close()
    return results


def compute_statistics(results: Dict) -> Dict[str, float]:
    """Compute summary statistics from results."""
    coverages = results['final_coverages']
    tx_counts = results['transactions_to_full_coverage']
    times = results['wall_times']

    return {
        'avg_final_coverage': float(np.mean(coverages)),
        'std_final_coverage': float(np.std(coverages)),
        'avg_transactions_to_100': float(np.mean(tx_counts)),
        'std_transactions_to_100': float(np.std(tx_counts)),
        'min_transactions_to_100': float(np.min(tx_counts)),
        'max_transactions_to_100': float(np.max(tx_counts)),
        'avg_wall_time': float(np.mean(times)),
        'episodes_reaching_100': sum(1 for c in coverages if c >= 100.0),
        'total_episodes': len(coverages),
    }


def generate_comparison_report(
    random_results: Dict,
    rl_results: Dict,
    algorithm: str,
    output_dir: str = "results",
) -> str:
    """Generate a comparison report."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    random_stats = compute_statistics(random_results)
    rl_stats = compute_statistics(rl_results)

    # Calculate improvement metrics
    if random_stats['avg_transactions_to_100'] > 0:
        tx_improvement = (
            (random_stats['avg_transactions_to_100'] - rl_stats['avg_transactions_to_100'])
            / random_stats['avg_transactions_to_100'] * 100
        )
    else:
        tx_improvement = 0.0

    speedup = (
        random_stats['avg_transactions_to_100'] / rl_stats['avg_transactions_to_100']
        if rl_stats['avg_transactions_to_100'] > 0 else float('inf')
    )

    report_lines = [
        "=" * 72,
        "ALU VERIFICATION: RL vs RANDOM COMPARISON REPORT",
        "=" * 72,
        "",
        f"RL Algorithm: {algorithm}",
        f"Training time: {rl_results.get('training_time', 0):.1f}s",
        "",
        "-" * 72,
        f"{'Metric':<40} {'Random':>14} {'RL':>14}",
        "-" * 72,
        f"{'Avg Final Coverage (%)':<40} {random_stats['avg_final_coverage']:>13.1f}% {rl_stats['avg_final_coverage']:>13.1f}%",
        f"{'Std Final Coverage':<40} {random_stats['std_final_coverage']:>14.2f} {rl_stats['std_final_coverage']:>14.2f}",
        f"{'Avg Transactions to 100%':<40} {random_stats['avg_transactions_to_100']:>14.0f} {rl_stats['avg_transactions_to_100']:>14.0f}",
        f"{'Min Transactions to 100%':<40} {random_stats['min_transactions_to_100']:>14.0f} {rl_stats['min_transactions_to_100']:>14.0f}",
        f"{'Max Transactions to 100%':<40} {random_stats['max_transactions_to_100']:>14.0f} {rl_stats['max_transactions_to_100']:>14.0f}",
        f"{'Episodes Reaching 100%':<40} {random_stats['episodes_reaching_100']:>14d} {rl_stats['episodes_reaching_100']:>14d}",
        f"{'Avg Wall Time (s)':<40} {random_stats['avg_wall_time']:>14.4f} {rl_stats['avg_wall_time']:>14.4f}",
        "-" * 72,
        "",
        "IMPROVEMENT SUMMARY:",
        f"  Transaction reduction: {tx_improvement:.1f}%",
        f"  Speedup factor:       {speedup:.2f}x",
        "",
        "=" * 72,
    ]

    report_text = "\n".join(report_lines)

    # Write report
    report_file = output_path / "comparison_report.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)

    # Write JSON data
    json_data = {
        'algorithm': algorithm,
        'random': random_stats,
        'rl': rl_stats,
        'improvement': {
            'transaction_reduction_pct': tx_improvement,
            'speedup_factor': speedup,
            'training_time': rl_results.get('training_time', 0),
        },
    }

    json_file = output_path / "comparison_results.json"
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2)

    # Generate coverage trajectory plot data (CSV for external plotting)
    csv_file = output_path / "coverage_trajectories.csv"
    with open(csv_file, 'w') as f:
        f.write("transaction,random_coverage,rl_coverage\n")
        # Use the first episode's trajectories for plotting
        random_traj = random_results['coverage_trajectories'][0] if random_results['coverage_trajectories'] else []
        rl_traj = rl_results['coverage_trajectories'][0] if rl_results['coverage_trajectories'] else []
        max_len = max(len(random_traj), len(rl_traj))
        for i in range(max_len):
            r_val = random_traj[i] if i < len(random_traj) else (random_traj[-1] if random_traj else 0)
            rl_val = rl_traj[i] if i < len(rl_traj) else (rl_traj[-1] if rl_traj else 0)
            f.write(f"{i+1},{r_val:.4f},{rl_val:.4f}\n")

    logger.info(f"Report saved to {report_file}")
    logger.info(f"JSON data saved to {json_file}")
    logger.info(f"Trajectory CSV saved to {csv_file}")

    return report_text


def try_generate_plot(output_dir: str = "results"):
    """Try to generate a matplotlib plot if available."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd

        csv_path = Path(output_dir) / "coverage_trajectories.csv"
        if not csv_path.exists():
            return

        df = pd.read_csv(csv_path)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df['transaction'], df['random_coverage'],
                label='Random/Constrained-Random', color='blue', alpha=0.7)
        ax.plot(df['transaction'], df['rl_coverage'],
                label='RL-Guided (PPO)', color='red', alpha=0.7)
        ax.set_xlabel('Transaction Number')
        ax.set_ylabel('Coverage (%)')
        ax.set_title('ALU Verification: Coverage Closure Comparison')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)

        plot_path = Path(output_dir) / "coverage_comparison.png"
        fig.savefig(str(plot_path), dpi=150, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Plot saved to {plot_path}")
    except ImportError:
        logger.warning("matplotlib/pandas not available, skipping plot generation")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare RL vs Random for ALU verification"
    )
    parser.add_argument('--algorithm', '-a', default='PPO',
                        choices=['PPO', 'DQN', 'A2C'])
    parser.add_argument('--timesteps', '-t', type=int, default=50000,
                        help='Training timesteps for RL agent')
    parser.add_argument('--max-transactions', '-m', type=int, default=5000,
                        help='Max transactions per episode')
    parser.add_argument('--episodes', '-e', type=int, default=10,
                        help='Number of evaluation episodes')
    parser.add_argument('--seed', '-s', type=int, default=42)
    parser.add_argument('--output-dir', '-o', default='results')
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("ALU Verification: RL vs Random Comparison")
    logger.info("=" * 60)

    # Run random baseline
    logger.info("\n--- Running Random Baseline ---")
    random_results = run_random_baseline(
        num_transactions=args.max_transactions,
        num_episodes=args.episodes,
        seed=args.seed,
        weighted=True,
    )

    # Run RL agent
    logger.info(f"\n--- Running RL Agent ({args.algorithm}) ---")
    rl_results = run_rl_agent(
        algorithm=args.algorithm,
        num_transactions=args.max_transactions,
        num_episodes=args.episodes,
        training_timesteps=args.timesteps,
        seed=args.seed,
    )

    # Generate report
    logger.info("\n--- Generating Report ---")
    report = generate_comparison_report(
        random_results, rl_results,
        algorithm=args.algorithm,
        output_dir=args.output_dir,
    )
    print("\n" + report)

    # Try to generate plot
    try_generate_plot(args.output_dir)

    logger.info("Comparison complete.")


if __name__ == '__main__':
    main()
