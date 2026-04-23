#!/usr/bin/env bash
# Full RL-vs-Random comparison pipeline (offline, no simulator needed).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ALGO=${ALGO:-PPO}
STEPS=${STEPS:-30000}
MAX_STEPS=${MAX_STEPS:-2000}
EPISODES=${EPISODES:-5}
SEED=${SEED:-0}

echo "[compare] algo=$ALGO steps=$STEPS max_steps=$MAX_STEPS episodes=$EPISODES"

make py-train   ALGO="$ALGO" STEPS="$STEPS" MAX_STEPS=500 SEED="$SEED"
make py-eval    ALGO="$ALGO" EPISODES="$EPISODES" MAX_STEPS="$MAX_STEPS" \
                MODEL="models/$(echo "$ALGO" | tr A-Z a-z)/$(echo "$ALGO" | tr A-Z a-z)_final.zip"
make py-random  EPISODES="$EPISODES" MAX_STEPS="$MAX_STEPS" SEED="$SEED"
make py-compare MAX_STEPS="$MAX_STEPS"

echo "[compare] done - see docs/results/COMPARISON.md and compare.png"
