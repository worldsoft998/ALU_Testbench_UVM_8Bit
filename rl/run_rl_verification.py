#!/usr/bin/env python3
"""
RL Verification Runner
========================
End-to-end script that:
1. Trains (or loads) an RL agent
2. Generates optimized stimuli
3. Writes stimuli file for SV simulation
4. Optionally launches SV simulation via subprocess
5. Reads back results and reports coverage

Usage:
    python -m rl.run_rl_verification --mode train-and-generate
    python -m rl.run_rl_verification --mode generate-only --model models/alu_rl_ppo_final
    python -m rl.run_rl_verification --mode live --pipe-dir /tmp/alu_rl_bridge
"""

import argparse
import logging
import json
import subprocess
import time
import os
import sys
from pathlib import Path

from .rl_agent import RLVerificationAgent, RandomBaselineAgent
from .bridge import PyHDLBridge, FileBridge
from .alu_gym_env import ALUVerifEnv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def train_and_generate(args):
    """Train RL agent and generate stimulus file."""
    agent = RLVerificationAgent(
        algorithm=args.algorithm,
        max_transactions=args.max_transactions,
        target_coverage=100.0,
        seed=args.seed,
        model_dir=args.model_dir,
        log_dir=args.log_dir,
    )

    # Train
    logger.info(f"Training {args.algorithm} for {args.timesteps} timesteps...")
    results = agent.train(total_timesteps=args.timesteps)
    logger.info(f"Training complete. Best coverage: {results['best_coverage']:.1f}%")

    # Generate stimuli
    stimuli = agent.generate_stimuli(
        num_transactions=args.num_stimuli,
        deterministic=True,
    )

    # Write to file
    bridge = FileBridge(work_dir=args.work_dir)
    stim_path = bridge.write_stimuli(stimuli)
    logger.info(f"Wrote {len(stimuli)} stimuli to {stim_path}")

    agent.close()
    return stim_path


def generate_only(args):
    """Generate stimuli from a pre-trained model."""
    agent = RLVerificationAgent(
        algorithm=args.algorithm,
        max_transactions=args.max_transactions,
        target_coverage=100.0,
        seed=args.seed,
    )
    agent.setup_environments()
    agent.load_model(args.model_path)

    stimuli = agent.generate_stimuli(
        num_transactions=args.num_stimuli,
        deterministic=True,
    )

    bridge = FileBridge(work_dir=args.work_dir)
    stim_path = bridge.write_stimuli(stimuli)
    logger.info(f"Wrote {len(stimuli)} stimuli to {stim_path}")

    agent.close()
    return stim_path


def generate_random(args):
    """Generate random stimuli for baseline comparison."""
    agent = RandomBaselineAgent(seed=args.seed)
    stimuli = agent.generate_stimuli(
        num_transactions=args.num_stimuli,
        weighted=True,
    )

    bridge = FileBridge(work_dir=args.work_dir)
    stim_path = bridge.write_stimuli(stimuli)
    logger.info(f"Wrote {len(stimuli)} random stimuli to {stim_path}")

    return stim_path


def live_mode(args):
    """
    Run in live mode with named-pipe bridge to SV simulation.

    The RL agent sends stimuli and receives responses in real-time
    from a running VCS simulation.
    """
    bridge = PyHDLBridge(
        pipe_dir=args.pipe_dir,
        timeout=args.timeout,
    )

    env = ALUVerifEnv(
        bridge=bridge,
        max_transactions=args.max_transactions,
        target_coverage=100.0,
        offline_mode=False,
    )

    # Load or create agent
    agent = RLVerificationAgent(
        algorithm=args.algorithm,
        max_transactions=args.max_transactions,
        target_coverage=100.0,
        seed=args.seed,
    )

    if args.model_path:
        agent.setup_environments()
        agent.load_model(args.model_path)
    else:
        logger.info("No pre-trained model specified, training first...")
        agent.train(total_timesteps=args.timesteps)

    # Connect bridge
    logger.info("Connecting bridge (waiting for SV simulation)...")
    bridge.connect(as_server=True)

    # Send initial reset
    bridge.send_stimulus(0, 0, 0, 0, reset=1)

    try:
        obs, info = env.reset(seed=args.seed)
        for step in range(args.num_stimuli):
            action, _ = agent.model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)

            if step % 100 == 0:
                logger.info(
                    f"Step {step}: coverage={info['coverage']:.1f}%, "
                    f"reward={reward:.2f}"
                )

            if terminated:
                logger.info(f"Target coverage reached at step {step}")
                break

    except (StopIteration, TimeoutError) as e:
        logger.info(f"Simulation ended: {e}")
    finally:
        bridge.disconnect()
        bridge.cleanup_pipes()

    agent.close()
    logger.info("Live mode complete")


def parse_args():
    parser = argparse.ArgumentParser(
        description="ALU RL Verification Runner"
    )
    parser.add_argument(
        '--mode',
        choices=['train-and-generate', 'generate-only', 'random', 'live'],
        default='train-and-generate',
        help='Operation mode'
    )
    parser.add_argument('--algorithm', '-a', default='PPO',
                        choices=['PPO', 'DQN', 'A2C'])
    parser.add_argument('--timesteps', '-t', type=int, default=50000)
    parser.add_argument('--max-transactions', type=int, default=5000)
    parser.add_argument('--num-stimuli', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--work-dir', default='sim_work')
    parser.add_argument('--model-dir', default='models')
    parser.add_argument('--log-dir', default='logs')
    parser.add_argument('--model-path', default=None,
                        help='Path to pre-trained model (for generate-only/live)')
    parser.add_argument('--pipe-dir', default='/tmp/alu_rl_bridge',
                        help='Named pipe directory (for live mode)')
    parser.add_argument('--timeout', type=float, default=30.0,
                        help='Bridge timeout in seconds')
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info(f"ALU RL Verification - Mode: {args.mode}")

    if args.mode == 'train-and-generate':
        train_and_generate(args)
    elif args.mode == 'generate-only':
        if not args.model_path:
            logger.error("--model-path required for generate-only mode")
            sys.exit(1)
        generate_only(args)
    elif args.mode == 'random':
        generate_random(args)
    elif args.mode == 'live':
        live_mode(args)


if __name__ == '__main__':
    main()
