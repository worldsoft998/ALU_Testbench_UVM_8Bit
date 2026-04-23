"""Train a stable-baselines3 policy on the ALU coverage env.

Usage
-----
    python -m rl.train --algo PPO --steps 50000 --out models/ppo
    python -m rl.train --algo DQN --steps 50000 --out models/dqn
    python -m rl.train --algo A2C --steps 50000 --out models/a2c

The ``--bridge`` flag switches training to the live UVM bridge env.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Type

from stable_baselines3 import A2C, DQN, PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from .alu_env import AluCoverageEnv

# DQN requires a Discrete action space, so we give it a flattened wrapper.
import gymnasium as gym
import numpy as np
from gymnasium import spaces


class _FlattenDiscreteActionWrapper(gym.ActionWrapper):
    """Wrap a MultiDiscrete action space into a single Discrete.

    Enumerates the product of sub-action spaces. The ALU env has
    6 * 256 * 256 * 2 * 2 ~= 1.5M actions which is large but still
    tractable for DQN training budgets in the tens of thousands of steps.
    Reduces the A/B sub-spaces to 16 quantised values to keep the table
    small enough for DQN.
    """

    def __init__(self, env: gym.Env, ab_quant: int = 16) -> None:
        super().__init__(env)
        self.ab_quant = int(ab_quant)
        self._dims = [6, self.ab_quant, self.ab_quant, 2, 2]
        self._nvec = np.array(self._dims, dtype=np.int64)
        self._total = int(np.prod(self._nvec))
        self.action_space = spaces.Discrete(self._total)

    def action(self, a: int) -> np.ndarray:
        idx = int(a)
        out = []
        for d in self._dims:
            out.append(idx % d)
            idx //= d
        op, ab, bb, cin, rst = out
        a_val = int(ab * (256 // self.ab_quant))
        b_val = int(bb * (256 // self.ab_quant))
        return np.array([op, a_val, b_val, cin, rst], dtype=np.int64)


_ALGOS: Dict[str, Type[Any]] = {
    "PPO": PPO,
    "DQN": DQN,
    "A2C": A2C,
}


def make_env(
    *,
    max_steps: int,
    target_coverage: float,
    flatten_for_dqn: bool,
) -> gym.Env:
    env = AluCoverageEnv(max_steps=max_steps, target_coverage=target_coverage)
    if flatten_for_dqn:
        env = _FlattenDiscreteActionWrapper(env)
    env = Monitor(env)
    return env


def build_model(algo: str, env: gym.Env, seed: int, out_dir: Path) -> Any:
    cls = _ALGOS[algo]
    policy = "MlpPolicy"
    common_kwargs: Dict[str, Any] = dict(
        policy=policy,
        env=env,
        verbose=1,
        seed=seed,
        tensorboard_log=str(out_dir / "tb"),
    )
    if algo == "DQN":
        common_kwargs.update(
            learning_rate=1e-3,
            buffer_size=50_000,
            learning_starts=1_000,
            batch_size=64,
            exploration_fraction=0.3,
            exploration_final_eps=0.05,
        )
    elif algo == "PPO":
        common_kwargs.update(
            learning_rate=3e-4,
            n_steps=256,
            batch_size=64,
            n_epochs=5,
        )
    elif algo == "A2C":
        common_kwargs.update(
            learning_rate=7e-4,
            n_steps=64,
        )
    return cls(**common_kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Train SB3 RL policy for ALU coverage")
    ap.add_argument("--algo", choices=list(_ALGOS.keys()), default="PPO")
    ap.add_argument("--steps", type=int, default=50_000)
    ap.add_argument("--max-steps", type=int, default=500,
                    help="Steps per episode.")
    ap.add_argument("--target-coverage", type=float, default=100.0)
    ap.add_argument("--out", type=Path, default=Path("models/ppo"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--checkpoint-every", type=int, default=10_000)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    flatten = args.algo == "DQN"
    env = DummyVecEnv([
        lambda: make_env(
            max_steps=args.max_steps,
            target_coverage=args.target_coverage,
            flatten_for_dqn=flatten,
        )
    ])

    model = build_model(args.algo, env, args.seed, args.out)

    cb = CheckpointCallback(
        save_freq=max(1, args.checkpoint_every),
        save_path=str(args.out / "checkpoints"),
        name_prefix=f"{args.algo.lower()}_alu",
    )

    model.learn(total_timesteps=args.steps, callback=cb, progress_bar=False)

    final_path = args.out / f"{args.algo.lower()}_final.zip"
    model.save(str(final_path))
    print(f"[train] saved {final_path}")


if __name__ == "__main__":
    main()
