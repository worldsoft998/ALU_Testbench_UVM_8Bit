"""
RL agent wrappers around stable-baselines3 algorithms for coverage
optimization.  Supports PPO, DQN, and A2C with a unified interface.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from stable_baselines3 import PPO, DQN, A2C
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from ai.environments.alu_coverage_env import ALUCoverageEnv
from ai.core.config import RLConfig


# ---------------------------------------------------------------------------
# Coverage-tracking callback
# ---------------------------------------------------------------------------

class CoverageCallback(BaseCallback):
    """Logs coverage metrics during training."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_coverages: list[float] = []
        self.episode_transactions: list[int] = []
        self.episode_steps: list[int] = []
        self._current_ep_start_step = 0

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            if "episode" in info:
                cov = info.get("coverage_pct", 0.0)
                txns = info.get("total_transactions", 0)
                self.episode_coverages.append(cov)
                self.episode_transactions.append(txns)
                self.episode_steps.append(self.num_timesteps)
                if self.verbose > 0:
                    print(
                        f"  [Ep {len(self.episode_coverages):4d}] "
                        f"Cov={cov:5.1f}%  Txns={txns:,}"
                    )
        return True

    def get_summary(self) -> dict[str, Any]:
        if not self.episode_coverages:
            return {}
        return {
            "mean_final_coverage": float(np.mean(self.episode_coverages)),
            "max_final_coverage": float(np.max(self.episode_coverages)),
            "mean_transactions": float(np.mean(self.episode_transactions)),
            "num_episodes": len(self.episode_coverages),
        }


# ---------------------------------------------------------------------------
# Unified agent interface
# ---------------------------------------------------------------------------

ALGORITHM_MAP = {
    "ppo": PPO,
    "dqn": DQN,
    "a2c": A2C,
}


class CoverageAgent:
    """
    Unified wrapper for training and using RL agents that optimise coverage.

    Parameters
    ----------
    algorithm : str
        One of 'ppo', 'dqn', 'a2c'.
    env_kwargs : dict
        Passed to ``ALUCoverageEnv.__init__``.
    rl_config : RLConfig, optional
        Hyperparameters.  Defaults to sensible values for the ALU task.
    """

    def __init__(
        self,
        algorithm: str = "ppo",
        env_kwargs: Optional[dict] = None,
        rl_config: Optional[RLConfig] = None,
    ):
        self.algorithm_name = algorithm.lower()
        if self.algorithm_name not in ALGORITHM_MAP:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. Choose from {list(ALGORITHM_MAP)}"
            )

        self.rl_config = rl_config or RLConfig(algorithm=self.algorithm_name)
        self.env_kwargs = env_kwargs or {}

        self._env: Optional[DummyVecEnv] = None
        self._model: Optional[PPO | DQN | A2C] = None
        self._callback: Optional[CoverageCallback] = None

    # -- environment -------------------------------------------------------

    def _make_env(self) -> DummyVecEnv:
        def _factory():
            env = ALUCoverageEnv(**self.env_kwargs)
            env = Monitor(env)
            return env
        return DummyVecEnv([_factory])

    # -- training ----------------------------------------------------------

    def train(
        self,
        total_timesteps: Optional[int] = None,
        save_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Train the agent and return a summary dict."""
        self._env = self._make_env()
        self._callback = CoverageCallback(verbose=self.rl_config.verbose)

        algo_cls = ALGORITHM_MAP[self.algorithm_name]
        timesteps = total_timesteps or self.rl_config.total_timesteps

        model_kwargs = self._build_model_kwargs()
        self._model = algo_cls(
            policy=self.rl_config.policy,
            env=self._env,
            seed=self.rl_config.seed,
            device=self.rl_config.device,
            verbose=self.rl_config.verbose,
            **model_kwargs,
        )

        self._model.learn(
            total_timesteps=timesteps,
            callback=self._callback,
        )

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            self._model.save(save_path)

        summary = self._callback.get_summary()
        summary["algorithm"] = self.algorithm_name
        summary["total_timesteps"] = timesteps
        return summary

    def _build_model_kwargs(self) -> dict:
        cfg = self.rl_config
        if self.algorithm_name == "ppo":
            return {
                "learning_rate": cfg.learning_rate,
                "gamma": cfg.gamma,
                "n_steps": cfg.n_steps,
                "batch_size": cfg.batch_size,
                "n_epochs": cfg.n_epochs,
            }
        elif self.algorithm_name == "a2c":
            return {
                "learning_rate": cfg.learning_rate,
                "gamma": cfg.gamma,
                "n_steps": cfg.n_steps,
            }
        elif self.algorithm_name == "dqn":
            return {
                "learning_rate": cfg.learning_rate,
                "gamma": cfg.gamma,
                "batch_size": cfg.batch_size,
                "buffer_size": cfg.buffer_size,
                "exploration_fraction": cfg.exploration_fraction,
                "exploration_final_eps": cfg.exploration_final_eps,
                "target_update_interval": cfg.target_update_interval,
            }
        return {}

    # -- inference / evaluation -------------------------------------------

    def load(self, path: str) -> None:
        algo_cls = ALGORITHM_MAP[self.algorithm_name]
        self._env = self._make_env()
        self._model = algo_cls.load(path, env=self._env)

    def predict(self, obs: np.ndarray, deterministic: bool = True) -> int:
        if self._model is None:
            raise RuntimeError("Model not trained or loaded.")
        action, _ = self._model.predict(obs, deterministic=deterministic)
        return int(action)

    def evaluate(
        self, n_episodes: int = 10
    ) -> dict[str, Any]:
        """Run *n_episodes* greedy roll-outs and return statistics."""
        if self._model is None:
            raise RuntimeError("Model not trained or loaded.")

        env = ALUCoverageEnv(**self.env_kwargs)
        coverages: list[float] = []
        transactions: list[int] = []
        steps_list: list[int] = []

        for ep in range(n_episodes):
            obs, info = env.reset(seed=self.rl_config.seed + ep)
            done = False
            step = 0
            while not done:
                action = self.predict(obs, deterministic=True)
                obs, _, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                step += 1
            coverages.append(info.get("coverage_pct", 0.0))
            transactions.append(info.get("total_transactions", 0))
            steps_list.append(step)

        return {
            "algorithm": self.algorithm_name,
            "n_episodes": n_episodes,
            "mean_coverage": float(np.mean(coverages)),
            "std_coverage": float(np.std(coverages)),
            "max_coverage": float(np.max(coverages)),
            "mean_transactions": float(np.mean(transactions)),
            "mean_steps": float(np.mean(steps_list)),
            "coverages": coverages,
            "transactions": transactions,
        }


# ---------------------------------------------------------------------------
# Random baseline agent
# ---------------------------------------------------------------------------

class RandomBaselineAgent:
    """
    Non-AI baseline that uses purely random seeds and default UVM stimulus
    distribution.  Provides the comparison benchmark.
    """

    def __init__(self, env_kwargs: Optional[dict] = None, seed: int = 42):
        self.env_kwargs = env_kwargs or {}
        self.seed = seed

    def evaluate(self, n_episodes: int = 10) -> dict[str, Any]:
        env = ALUCoverageEnv(**self.env_kwargs)
        rng = np.random.RandomState(self.seed)
        coverages: list[float] = []
        transactions: list[int] = []
        steps_list: list[int] = []

        for ep in range(n_episodes):
            obs, _ = env.reset(seed=self.seed + ep)
            done = False
            step = 0
            while not done:
                action = int(rng.randint(0, env.action_space.n))
                obs, _, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                step += 1
            coverages.append(info.get("coverage_pct", 0.0))
            transactions.append(info.get("total_transactions", 0))
            steps_list.append(step)

        return {
            "algorithm": "random_baseline",
            "n_episodes": n_episodes,
            "mean_coverage": float(np.mean(coverages)),
            "std_coverage": float(np.std(coverages)),
            "max_coverage": float(np.max(coverages)),
            "mean_transactions": float(np.mean(transactions)),
            "mean_steps": float(np.mean(steps_list)),
            "coverages": coverages,
            "transactions": transactions,
        }
