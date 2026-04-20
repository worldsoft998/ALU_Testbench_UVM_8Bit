#!/usr/bin/env python3
"""
RL Training Entry Point
========================
Train an RL agent for ALU verification stimulus optimization.

Usage:
    python -m rl.train --algorithm PPO --timesteps 100000
    python -m rl.train --algorithm DQN --timesteps 50000 --n-envs 4
    python -m rl.train --algorithm A2C --timesteps 80000 --seed 123
"""

import argparse
import logging
import json
import sys
import os
from pathlib import Path

from .rl_agent import RLVerificationAgent, ALGORITHMS
from .bridge import FileBridge

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train RL agent for ALU verification optimization"
    )
    parser.add_argument(
        '--algorithm', '-a',
        type=str,
        default='PPO',
        choices=list(ALGORITHMS.keys()),
        help='RL algorithm to use (default: PPO)'
    )
    parser.add_argument(
        '--timesteps', '-t',
        type=int,
        default=100000,
        help='Total training timesteps (default: 100000)'
    )
    parser.add_argument(
        '--max-transactions', '-m',
        type=int,
        default=5000,
        help='Max transactions per episode (default: 5000)'
    )
    parser.add_argument(
        '--target-coverage',
        type=float,
        default=100.0,
        help='Target coverage percentage (default: 100.0)'
    )
    parser.add_argument(
        '--n-envs', '-n',
        type=int,
        default=1,
        help='Number of parallel environments (default: 1)'
    )
    parser.add_argument(
        '--seed', '-s',
        type=int,
        default=42,
        help='Random seed (default: 42)'
    )
    parser.add_argument(
        '--model-dir',
        type=str,
        default='models',
        help='Directory to save models (default: models)'
    )
    parser.add_argument(
        '--log-dir',
        type=str,
        default='logs',
        help='Directory for training logs (default: logs)'
    )
    parser.add_argument(
        '--generate-stimuli',
        type=int,
        default=0,
        help='Generate N stimuli after training (0=skip)'
    )
    parser.add_argument(
        '--output-stim-file',
        type=str,
        default='sim_work/rl_stimuli.txt',
        help='Output file for generated stimuli'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=None,
        help='Override learning rate'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help='Override batch size'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info(f"ALU RL Training - Algorithm: {args.algorithm}")
    logger.info(f"Timesteps: {args.timesteps}, Seed: {args.seed}")

    # Build hyperparameter overrides
    hyperparams = {}
    if args.learning_rate is not None:
        hyperparams['learning_rate'] = args.learning_rate
    if args.batch_size is not None:
        hyperparams['batch_size'] = args.batch_size

    # Create and train agent
    agent = RLVerificationAgent(
        algorithm=args.algorithm,
        hyperparams=hyperparams if hyperparams else None,
        max_transactions=args.max_transactions,
        target_coverage=args.target_coverage,
        n_envs=args.n_envs,
        model_dir=args.model_dir,
        log_dir=args.log_dir,
        seed=args.seed,
    )

    results = agent.train(total_timesteps=args.timesteps)

    logger.info("=== Training Results ===")
    logger.info(f"Best coverage: {results['best_coverage']:.1f}%")
    logger.info(f"Training time: {results['training_time_seconds']:.1f}s")
    logger.info(
        f"Avg transactions to target: "
        f"{results['avg_transactions_to_target']:.0f}"
    )

    # Generate stimuli if requested
    if args.generate_stimuli > 0:
        logger.info(f"Generating {args.generate_stimuli} optimized stimuli...")
        stimuli = agent.generate_stimuli(
            num_transactions=args.generate_stimuli,
            deterministic=True,
        )

        # Write to file for SV simulation
        bridge = FileBridge(work_dir=os.path.dirname(args.output_stim_file))
        bridge.stim_file = Path(args.output_stim_file)
        bridge.write_stimuli(stimuli)

        logger.info(f"Stimuli written to {args.output_stim_file}")

    agent.close()
    logger.info("Training complete.")


if __name__ == '__main__':
    main()
