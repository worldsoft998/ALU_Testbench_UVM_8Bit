"""Pure-random stimulus baseline (same env, uniformly-random actions)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from .alu_env import AluCoverageEnv


def run_episode(env: AluCoverageEnv, max_steps: int, rng: np.random.Generator) -> Dict[str, Any]:
    env.reset(seed=int(rng.integers(0, 2**31 - 1)))
    steps_to_100 = -1
    trace: List[float] = []
    cumulative_reward = 0.0
    for step in range(max_steps):
        action = env.action_space.sample()
        _, r, terminated, truncated, info = env.step(action)
        cumulative_reward += float(r)
        trace.append(float(info["coverage_pct"]))
        if steps_to_100 < 0 and info["coverage_pct"] >= 100.0:
            steps_to_100 = step + 1
        if terminated or truncated:
            break
    return {
        "reward": cumulative_reward,
        "final_coverage": trace[-1] if trace else 0.0,
        "steps_to_100": steps_to_100,
        "coverage_trace": trace,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("docs/results/random_eval.json"))
    ap.add_argument("--csv", type=Path, default=Path("docs/results/random_eval.csv"))
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    env = AluCoverageEnv(max_steps=args.max_steps)
    results = [run_episode(env, args.max_steps, rng) for _ in range(args.episodes)]

    summary = {
        "algo": "RANDOM",
        "episodes": args.episodes,
        "mean_final_coverage": float(np.mean([r["final_coverage"] for r in results])),
        "mean_steps_to_100": float(np.mean([
            r["steps_to_100"] if r["steps_to_100"] > 0 else args.max_steps
            for r in results
        ])),
        "per_episode": results,
    }
    args.out.write_text(json.dumps(summary, indent=2))
    with args.csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode", "step", "coverage_pct"])
        for i, r in enumerate(results):
            for step, cov in enumerate(r["coverage_trace"]):
                w.writerow([i, step, f"{cov:.4f}"])

    print(json.dumps(
        {k: v for k, v in summary.items() if k != "per_episode"},
        indent=2,
    ))


if __name__ == "__main__":
    main()
