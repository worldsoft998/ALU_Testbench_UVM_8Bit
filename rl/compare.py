"""Produce a side-by-side comparison of RL vs random stimulus runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import numpy as np


def _load(path: Path) -> Dict:
    return json.loads(path.read_text())


def _mean_curve(eps: List[Dict], horizon: int) -> List[float]:
    """Mean coverage curve across episodes, padded with the last value."""
    traces: List[List[float]] = [e["coverage_trace"] for e in eps]
    padded = []
    for t in traces:
        pad = t + [t[-1] if t else 0.0] * (horizon - len(t))
        padded.append(pad[:horizon])
    arr = np.array(padded, dtype=np.float32)
    return arr.mean(axis=0).tolist()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rl", type=Path, default=Path("docs/results/rl_eval.json"))
    ap.add_argument("--random", type=Path, default=Path("docs/results/random_eval.json"))
    ap.add_argument("--out-json", type=Path, default=Path("docs/results/compare.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("docs/results/compare.csv"))
    ap.add_argument("--out-md", type=Path, default=Path("docs/results/COMPARISON.md"))
    ap.add_argument("--plot", type=Path, default=Path("docs/results/compare.png"))
    ap.add_argument("--horizon", type=int, default=2000)
    args = ap.parse_args()

    args.out_json.parent.mkdir(parents=True, exist_ok=True)

    rl = _load(args.rl)
    rnd = _load(args.random)

    rl_curve = _mean_curve(rl["per_episode"], args.horizon)
    rnd_curve = _mean_curve(rnd["per_episode"], args.horizon)

    comparison = {
        "rl": {k: v for k, v in rl.items() if k != "per_episode"},
        "random": {k: v for k, v in rnd.items() if k != "per_episode"},
        "delta_mean_final_coverage": rl["mean_final_coverage"] - rnd["mean_final_coverage"],
        "speedup_steps_to_100": (
            (rnd["mean_steps_to_100"] / max(1.0, rl["mean_steps_to_100"]))
            if rl["mean_steps_to_100"] > 0
            else None
        ),
    }
    args.out_json.write_text(json.dumps(comparison, indent=2))

    with args.out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "rl_mean_cov_pct", "random_mean_cov_pct"])
        for i, (a, b) in enumerate(zip(rl_curve, rnd_curve)):
            w.writerow([i, f"{a:.3f}", f"{b:.3f}"])

    md_lines = [
        "# RL vs Random Stimulus - ALU Coverage Closure",
        "",
        "| metric | RL (`{algo}`) | Random |".format(algo=rl["algo"]),
        "|---|---|---|",
        "| episodes | {} | {} |".format(rl["episodes"], rnd["episodes"]),
        "| mean final coverage (%) | {:.2f} | {:.2f} |".format(
            rl["mean_final_coverage"], rnd["mean_final_coverage"]
        ),
        "| mean steps to 100% | {:.1f} | {:.1f} |".format(
            rl["mean_steps_to_100"], rnd["mean_steps_to_100"]
        ),
        "| coverage-closure speed-up | {:.2f}x |".format(
            comparison["speedup_steps_to_100"] or 0.0
        ),
        "",
        "Coverage vs step curves are plotted in `compare.png`.",
    ]
    args.out_md.write_text("\n".join(md_lines))

    # Plot
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(rl_curve, label=f"RL ({rl['algo']})", linewidth=2)
        ax.plot(rnd_curve, label="Random", linewidth=2, linestyle="--")
        ax.set_xlabel("Stimulus step")
        ax.set_ylabel("Functional coverage (%)")
        ax.set_title("ALU functional coverage vs. stimuli")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.plot, dpi=140)
        print(f"[compare] plot saved to {args.plot}")
    except Exception as exc:  # pragma: no cover - plotting optional
        print(f"[compare] plot skipped: {exc}")

    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
