"""
RL Agent Wrapper using Stable-Baselines3
==========================================
Provides a unified interface for training and using RL agents
(PPO, DQN, A2C) for ALU verification stimulus optimization.

Supports:
    - Multiple algorithms (PPO, DQN, A2C)
    - Training with configurable hyperparameters
    - Model save/load for reuse across simulation runs
    - Stimulus generation from trained models
    - Multi-threaded sampling via SubprocVecEnv
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import numpy as np
import gymnasium as gym

from stable_baselines3 import PPO, DQN, A2C
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.logger import configure as sb3_configure

from .alu_gym_env import ALUVerifEnv, ALUVerifEnvContinuous

logger = logging.getLogger(__name__)

# Supported algorithms
ALGORITHMS = {
    'PPO': PPO,
    'DQN': DQN,
    'A2C': A2C,
}

# Default hyperparameters per algorithm
DEFAULT_HYPERPARAMS = {
    'PPO': {
        'learning_rate': 3e-4,
        'n_steps': 256,
        'batch_size': 64,
        'n_epochs': 10,
        'gamma': 0.99,
        'gae_lambda': 0.95,
        'clip_range': 0.2,
        'ent_coef': 0.01,
        'vf_coef': 0.5,
        'max_grad_norm': 0.5,
        'policy': 'MlpPolicy',
    },
    'DQN': {
        'learning_rate': 1e-4,
        'buffer_size': 50000,
        'learning_starts': 1000,
        'batch_size': 64,
        'gamma': 0.99,
        'target_update_interval': 500,
        'exploration_fraction': 0.3,
        'exploration_final_eps': 0.05,
        'policy': 'MlpPolicy',
    },
    'A2C': {
        'learning_rate': 7e-4,
        'n_steps': 5,
        'gamma': 0.99,
        'gae_lambda': 1.0,
        'ent_coef': 0.01,
        'vf_coef': 0.25,
        'max_grad_norm': 0.5,
        'policy': 'MlpPolicy',
    },
}


class CoverageCallback(BaseCallback):
    """
    Custom callback to track coverage progress during training.

    Logs coverage metrics and can trigger early stopping when
    target coverage is reached consistently.
    """

    def __init__(
        self,
        check_freq: int = 100,
        target_coverage: float = 100.0,
        patience: int = 5,
        log_dir: Optional[str] = None,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.target_coverage = target_coverage
        self.patience = patience
        self.log_dir = log_dir

        self.coverage_history: List[float] = []
        self.best_coverage = 0.0
        self.target_reached_count = 0
        self.episodes_completed = 0
        self.transactions_per_episode: List[int] = []

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq == 0:
            # Extract info from the environments
            infos = self.locals.get('infos', [])
            for info in infos:
                if 'coverage' in info:
                    cov = info['coverage']
                    self.coverage_history.append(cov)
                    self.best_coverage = max(self.best_coverage, cov)

                    if cov >= self.target_coverage:
                        self.target_reached_count += 1
                        tx_count = info.get('transaction_count', 0)
                        self.transactions_per_episode.append(tx_count)

                        if self.verbose:
                            logger.info(
                                f"Target coverage reached in {tx_count} transactions "
                                f"(count: {self.target_reached_count})"
                            )

            if self.verbose and self.coverage_history:
                recent_cov = np.mean(self.coverage_history[-10:])
                logger.info(
                    f"Step {self.n_calls}: "
                    f"Recent avg coverage: {recent_cov:.1f}%, "
                    f"Best: {self.best_coverage:.1f}%"
                )

        return True

    def get_results(self) -> Dict[str, Any]:
        """Return training results summary."""
        return {
            'best_coverage': self.best_coverage,
            'target_reached_count': self.target_reached_count,
            'avg_transactions_to_target': (
                np.mean(self.transactions_per_episode)
                if self.transactions_per_episode else float('inf')
            ),
            'min_transactions_to_target': (
                min(self.transactions_per_episode)
                if self.transactions_per_episode else float('inf')
            ),
            'coverage_history': self.coverage_history,
        }


class RLVerificationAgent:
    """
    RL agent for ALU verification optimization.

    Wraps stable-baselines3 algorithms and provides a clean interface
    for training, inference, and stimulus generation.
    """

    def __init__(
        self,
        algorithm: str = "PPO",
        hyperparams: Optional[Dict] = None,
        max_transactions: int = 5000,
        target_coverage: float = 100.0,
        n_envs: int = 1,
        model_dir: str = "models",
        log_dir: str = "logs",
        seed: int = 42,
    ):
        """
        Initialize the RL verification agent.

        Args:
            algorithm: RL algorithm name (PPO, DQN, A2C).
            hyperparams: Override default hyperparameters.
            max_transactions: Max transactions per episode.
            target_coverage: Target coverage percentage.
            n_envs: Number of parallel environments.
            model_dir: Directory for saving models.
            log_dir: Directory for training logs.
            seed: Random seed.
        """
        if algorithm not in ALGORITHMS:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. "
                f"Supported: {list(ALGORITHMS.keys())}"
            )

        self.algorithm_name = algorithm
        self.algorithm_class = ALGORITHMS[algorithm]

        # Merge default hyperparams with overrides
        self.hyperparams = DEFAULT_HYPERPARAMS[algorithm].copy()
        if hyperparams:
            self.hyperparams.update(hyperparams)

        self.max_transactions = max_transactions
        self.target_coverage = target_coverage
        self.n_envs = n_envs
        self.model_dir = Path(model_dir)
        self.log_dir = Path(log_dir)
        self.seed = seed

        self.model = None
        self.env = None
        self.callback = None

        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"RLVerificationAgent: algo={algorithm}, "
            f"n_envs={n_envs}, seed={seed}"
        )

    def _make_env(self, rank: int = 0) -> gym.Env:
        """Create a single ALU verification environment."""
        def _init():
            env = ALUVerifEnv(
                max_transactions=self.max_transactions,
                target_coverage=self.target_coverage,
                offline_mode=True,
            )
            env = Monitor(env, str(self.log_dir / f"env_{rank}"))
            return env
        return _init

    def setup_environments(self):
        """Create vectorized training environments."""
        if self.n_envs > 1:
            self.env = SubprocVecEnv(
                [self._make_env(i) for i in range(self.n_envs)]
            )
        else:
            self.env = DummyVecEnv([self._make_env(0)])

        logger.info(f"Created {self.n_envs} parallel environment(s)")

    def create_model(self):
        """Instantiate the RL model."""
        if self.env is None:
            self.setup_environments()

        policy = self.hyperparams.pop('policy', 'MlpPolicy')

        # DQN doesn't support n_steps and some other params
        algo_params = {k: v for k, v in self.hyperparams.items()}

        self.model = self.algorithm_class(
            policy,
            self.env,
            verbose=1,
            seed=self.seed,
            tensorboard_log=str(self.log_dir / "tensorboard"),
            **algo_params,
        )

        # Restore policy key for future reference
        self.hyperparams['policy'] = policy

        logger.info(f"Created {self.algorithm_name} model with policy={policy}")

    def train(
        self,
        total_timesteps: int = 100000,
        eval_freq: int = 5000,
        save_freq: int = 10000,
        callback_check_freq: int = 100,
    ) -> Dict[str, Any]:
        """
        Train the RL agent.

        Args:
            total_timesteps: Total training steps.
            eval_freq: Evaluation frequency.
            save_freq: Model checkpoint save frequency.
            callback_check_freq: Coverage callback check frequency.

        Returns:
            Training results dictionary.
        """
        if self.model is None:
            self.create_model()

        # Setup callbacks
        self.callback = CoverageCallback(
            check_freq=callback_check_freq,
            target_coverage=self.target_coverage,
            log_dir=str(self.log_dir),
        )

        logger.info(
            f"Starting training: {total_timesteps} timesteps, "
            f"algo={self.algorithm_name}"
        )
        start_time = time.time()

        self.model.learn(
            total_timesteps=total_timesteps,
            callback=self.callback,
            progress_bar=True,
        )

        training_time = time.time() - start_time

        # Save final model
        model_path = self.model_dir / f"alu_rl_{self.algorithm_name.lower()}_final"
        self.model.save(str(model_path))
        logger.info(f"Model saved to {model_path}")

        # Collect results
        results = self.callback.get_results()
        results['training_time_seconds'] = training_time
        results['algorithm'] = self.algorithm_name
        results['total_timesteps'] = total_timesteps
        results['hyperparams'] = self.hyperparams

        # Save results to JSON
        results_path = self.log_dir / "training_results.json"
        serializable = {
            k: (v if not isinstance(v, np.floating) else float(v))
            for k, v in results.items()
            if k != 'coverage_history'
        }
        serializable['coverage_history_len'] = len(results.get('coverage_history', []))
        with open(results_path, 'w') as f:
            json.dump(serializable, f, indent=2)

        logger.info(
            f"Training complete in {training_time:.1f}s. "
            f"Best coverage: {results['best_coverage']:.1f}%"
        )

        return results

    def generate_stimuli(
        self,
        num_transactions: int = 1000,
        deterministic: bool = True,
    ) -> List[Dict[str, int]]:
        """
        Generate optimized stimuli using the trained model.

        Args:
            num_transactions: Number of stimulus transactions to generate.
            deterministic: Use deterministic (greedy) policy.

        Returns:
            List of stimulus dictionaries.
        """
        if self.model is None:
            raise RuntimeError("Model not trained or loaded. Call train() or load() first.")

        # Create a fresh environment for generation
        env = ALUVerifEnv(
            max_transactions=num_transactions,
            target_coverage=self.target_coverage,
            offline_mode=True,
        )

        obs, info = env.reset(seed=self.seed)
        stimuli = []
        coverage_trajectory = []

        for _ in range(num_transactions):
            action, _ = self.model.predict(obs, deterministic=deterministic)
            obs, reward, terminated, truncated, info = env.step(action)

            stimuli.append(info['stimulus'].copy())
            coverage_trajectory.append(info['coverage'])

            if terminated:
                logger.info(
                    f"Target coverage reached at transaction "
                    f"{info['transaction_count']}"
                )
                break

        logger.info(
            f"Generated {len(stimuli)} stimuli. "
            f"Final coverage: {coverage_trajectory[-1]:.1f}%"
        )

        return stimuli

    def save_model(self, path: Optional[str] = None):
        """Save the trained model."""
        if self.model is None:
            raise RuntimeError("No model to save")
        save_path = path or str(
            self.model_dir / f"alu_rl_{self.algorithm_name.lower()}"
        )
        self.model.save(save_path)
        logger.info(f"Model saved to {save_path}")

    def load_model(self, path: str):
        """Load a previously trained model."""
        if self.env is None:
            self.setup_environments()

        self.model = self.algorithm_class.load(path, env=self.env)
        logger.info(f"Model loaded from {path}")

    def close(self):
        """Clean up environments."""
        if self.env is not None:
            self.env.close()
            self.env = None


class RandomBaselineAgent:
    """
    Random stimulus generator for comparison baseline.

    Generates purely random stimuli matching the ALU's input space
    with the same constraint distributions as the original UVM sequence.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)
        self.seed_val = seed

    def generate_stimuli(
        self,
        num_transactions: int = 1000,
        weighted: bool = True,
    ) -> List[Dict[str, int]]:
        """
        Generate random stimuli.

        Args:
            num_transactions: Number of transactions.
            weighted: Use weighted distribution matching UVM constraints.

        Returns:
            List of stimulus dictionaries.
        """
        stimuli = []

        for _ in range(num_transactions):
            if weighted:
                # Match the SV constraint: dist { 0xFF := 80, 0x0 := 80, [1:0xFE] := 10 }
                a_choice = self.rng.choice(
                    [0, 1, 2], p=[80/170, 80/170, 10/170]
                )
                if a_choice == 0:
                    A = 0xFF
                elif a_choice == 1:
                    A = 0x00
                else:
                    A = self.rng.randint(1, 0xFF)

                b_choice = self.rng.choice(
                    [0, 1, 2], p=[80/170, 80/170, 10/170]
                )
                if b_choice == 0:
                    B = 0xFF
                elif b_choice == 1:
                    B = 0x00
                else:
                    B = self.rng.randint(1, 0xFF)
            else:
                A = self.rng.randint(0, 256)
                B = self.rng.randint(0, 256)

            op_code = self.rng.randint(0, 6)
            C_in = self.rng.randint(0, 2)

            stimuli.append({
                'A': int(A),
                'B': int(B),
                'op_code': int(op_code),
                'C_in': int(C_in),
                'reset': 0,
            })

        return stimuli

    def run_coverage_analysis(
        self, num_transactions: int = 1000
    ) -> Dict[str, Any]:
        """
        Run random stimuli through the coverage model and return results.

        Args:
            num_transactions: Number of transactions.

        Returns:
            Coverage results dictionary.
        """
        env = ALUVerifEnv(
            max_transactions=num_transactions,
            target_coverage=100.0,
            offline_mode=True,
        )

        obs, info = env.reset(seed=self.seed_val)
        stimuli = self.generate_stimuli(num_transactions)
        coverage_trajectory = []

        for stim in stimuli:
            # Map stimulus to action categories
            a_cat = 1 if stim['A'] == 0xFF else (0 if stim['A'] == 0 else 2)
            b_cat = 1 if stim['B'] == 0xFF else (0 if stim['B'] == 0 else 2)
            action = np.array([a_cat, b_cat, stim['op_code'], stim['C_in']])

            obs, reward, terminated, truncated, info = env.step(action)
            coverage_trajectory.append(info['coverage'])

            if terminated:
                break

        return {
            'final_coverage': coverage_trajectory[-1] if coverage_trajectory else 0.0,
            'coverage_trajectory': coverage_trajectory,
            'transactions_used': len(coverage_trajectory),
            'stimuli': stimuli[:len(coverage_trajectory)],
        }
