"""Evaluate a trained SB3 policy on the ALU coverage env."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from stable_baselines3 import A2C, DQN, PPO

from .alu_env import AluCoverageEnv
from .train import _FlattenDiscreteActionWrapper

_ALGOS = {"PPO": PPO, "DQN": DQN, "A2C": A2C}


def run_episode(model: Any, env: AluCoverageEnv, max_steps: int) -> Dict[str, Any]:
    obs, _ = env.reset()
    steps_to_100 = -1
    coverage_trace: List[float] = []
    cumulative_reward = 0.0
    for step in range(max_steps):
        action, _ = model.predict(obs, deterministic=False)
        obs, r, terminated, truncated, info = env.step(action)
        cumulative_reward += float(r)
        coverage_trace.append(float(info["coverage_pct"]))
        if steps_to_100 < 0 and info["coverage_pct"] >= 100.0:
            steps_to_100 = step + 1
        if terminated or truncated:
            break
    return {
        "reward": cumulative_reward,
        "final_coverage": coverage_trace[-1] if coverage_trace else 0.0,
        "steps_to_100": steps_to_100,
        "coverage_trace": coverage_trace,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--algo", choices=list(_ALGOS.keys()), default="PPO")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=Path("docs/results/rl_eval.json"))
    ap.add_argument("--csv", type=Path, default=Path("docs/results/rl_eval.csv"))
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    flatten = args.algo == "DQN"
    env = AluCoverageEnv(max_steps=args.max_steps)
    if flatten:
        env = _FlattenDiscreteActionWrapper(env)

    model = _ALGOS[args.algo].load(str(args.model), env=env)

    all_results = [run_episode(model, env, args.max_steps) for _ in range(args.episodes)]

    summary = {
        "algo": args.algo,
        "episodes": args.episodes,
        "mean_final_coverage": float(np.mean([r["final_coverage"] for r in all_results])),
        "mean_steps_to_100": float(np.mean([
            r["steps_to_100"] if r["steps_to_100"] > 0 else args.max_steps
            for r in all_results
        ])),
        "per_episode": all_results,
    }

    args.out.write_text(json.dumps(summary, indent=2))
    with args.csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode", "step", "coverage_pct"])
        for i, r in enumerate(all_results):
            for step, cov in enumerate(r["coverage_trace"]):
                w.writerow([i, step, f"{cov:.4f}"])

    print(json.dumps(
        {k: v for k, v in summary.items() if k != "per_episode"},
        indent=2,
    ))


if __name__ == "__main__":
    main()
