#!/usr/bin/env python3
"""
Training Script for ALU Verification RL Agents
Trains reinforcement learning agents using Gymnasium and stable-baselines3

Author: AI Assistant
Date: 2026-04-24
"""

import argparse
import os
import sys
import time
import json
from datetime import datetime
from typing import Optional, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Train RL agents for ALU Verification'
    )
    
    parser.add_argument(
        '--algorithm',
        type=str,
        default='ppo',
        choices=['ppo', 'a2c', 'dqn', 'sac', 'td3', 'random'],
        help='RL algorithm to train (default: ppo)'
    )
    
    parser.add_argument(
        '--timesteps',
        type=int,
        default=100000,
        help='Total training timesteps (default: 100000)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='./models',
        help='Output directory for models'
    )
    
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Train all algorithms for comparison'
    )
    
    parser.add_argument(
        '--env-config',
        type=str,
        default=None,
        help='JSON file with environment configuration'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()


def load_env_config(config_path: Optional[str]) -> dict:
    """Load environment configuration from JSON file"""
    if config_path:
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def train_single_agent(
    algorithm: str,
    timesteps: int,
    output_dir: str,
    verbose: bool = True
) -> dict:
    """Train a single RL agent"""
    from RL.alu_rl_environment import create_alu_env
    from RL.rl_agents import (
        create_agent,
        AlgorithmType,
        TrainingConfig,
        TrainingStatisticsCallback
    )
    
    print(f"\n{'='*60}")
    print(f"Training {algorithm.upper()} Agent")
    print(f"{'='*60}")
    
    # Create environment
    env = create_alu_env()
    
    # Get algorithm type
    algo_map = {
        'ppo': AlgorithmType.PPO,
        'a2c': AlgorithmType.A2C,
        'dqn': AlgorithmType.DQN,
        'sac': AlgorithmType.SAC,
        'td3': AlgorithmType.TD3,
        'random': AlgorithmType.RANDOM
    }
    algo_type = algo_map.get(algorithm.lower(), AlgorithmType.PPO)
    
    # Create training configuration
    config = TrainingConfig()
    config.total_timesteps = timesteps
    config.learning_rate = 3e-4
    config.n_steps = 2048
    config.batch_size = 64
    config.coverage_target = 0.95
    
    # Create agent
    agent = create_agent(env, algo_type, output_dir, config)
    
    # Train
    start_time = time.time()
    
    if algo_type != AlgorithmType.RANDOM:
        stats = agent.train()
    else:
        # For random agent, just evaluate
        print("Evaluating random agent...")
        stats = {'mean_reward': 0, 'total_episodes': 0}
    
    training_time = time.time() - start_time
    
    # Save model
    model_path = os.path.join(output_dir, f'{algorithm}_model')
    agent.save(model_path)
    
    # Calculate final metrics
    final_coverage = env._get_coverage_percentage()
    max_coverage = max(env.coverage_history) if hasattr(env, 'coverage_history') else final_coverage
    
    result = {
        'algorithm': algorithm,
        'timesteps': timesteps,
        'training_time': training_time,
        'final_coverage': final_coverage,
        'max_coverage': max_coverage,
        'mean_reward': stats.get('mean_reward', 0),
        'episodes': stats.get('total_episodes', 0),
        'model_path': model_path
    }
    
    print(f"\nTraining Complete:")
    print(f"  Time: {training_time:.2f}s")
    print(f"  Final Coverage: {final_coverage:.2%}")
    print(f"  Max Coverage: {max_coverage:.2%}")
    print(f"  Mean Reward: {stats.get('mean_reward', 0):.2f}")
    
    return result


def train_all_agents(
    algorithms: List[str],
    timesteps: int,
    output_dir: str
) -> List[dict]:
    """Train multiple agents for comparison"""
    results = []
    
    for algo in algorithms:
        result = train_single_agent(algo, timesteps, output_dir)
        results.append(result)
    
    return results


def print_comparison(results: List[dict]):
    """Print comparison of trained agents"""
    print(f"\n{'='*80}")
    print("ALGORITHM COMPARISON")
    print(f"{'='*80}")
    print(f"{'Algorithm':<12} {'Time (s)':<12} {'Coverage':<12} {'Max Cov':<12} {'Mean Reward':<15}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['algorithm']:<12} {r['training_time']:<12.2f} "
              f"{r['final_coverage']:<12.2%} {r['max_coverage']:<12.2%} "
              f"{r['mean_reward']:<15.2f}")
    
    # Find best
    best_by_coverage = max(results, key=lambda x: x['max_coverage'])
    fastest = min(results, key=lambda x: x['training_time'])
    
    print(f"\nBest by Coverage: {best_by_coverage['algorithm']} ({best_by_coverage['max_coverage']:.2%})")
    print(f"Fastest: {fastest['algorithm']} ({fastest['training_time']:.2f}s)")


def save_results(results: List[dict], output_dir: str):
    """Save training results to JSON"""
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'training_results.json')
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'results': results
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")


def main():
    """Main training entry point"""
    args = parse_args()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    print(f"\n{'#'*60}")
    print("# ALU VERIFICATION RL TRAINING")
    print(f"{'#'*60}")
    print(f"Algorithm: {args.algorithm}")
    print(f"Timesteps: {args.timesteps}")
    print(f"Output: {args.output}")
    
    if args.compare:
        # Train all algorithms
        algorithms = ['ppo', 'a2c', 'dqn', 'random']
        results = train_all_agents(algorithms, args.timesteps, args.output)
        print_comparison(results)
    else:
        # Train single algorithm
        result = train_single_agent(
            args.algorithm,
            args.timesteps,
            args.output,
            args.verbose
        )
        results = [result]
    
    # Save results
    save_results(results, args.output)
    
    print(f"\n{'#'*60}")
    print("# TRAINING COMPLETE")
    print(f"{'#'*60}\n")


if __name__ == '__main__':
    main()