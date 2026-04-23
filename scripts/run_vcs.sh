#!/usr/bin/env bash
# Thin wrapper around the Makefile with sensible defaults for CI.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

TEST=${TEST:-alu_random_test}
ALGO=${ALGO:-PPO}
SEED=${SEED:-1}
NUM_ITEMS=${NUM_ITEMS:-5000}

echo "[run_vcs] TEST=$TEST ALGO=$ALGO SEED=$SEED NUM_ITEMS=$NUM_ITEMS"

if [[ "$TEST" == "alu_rl_test" ]]; then
    if [[ -z "${MODEL:-}" ]]; then
        echo "[run_vcs] MODEL not set; training a quick PPO policy first"
        make py-train ALGO="$ALGO" STEPS=10000 MAX_STEPS=500
        MODEL="models/$(echo "$ALGO" | tr A-Z a-z)/$(echo "$ALGO" | tr A-Z a-z)_final.zip"
        export MODEL
    fi
    make rl-sim TEST="$TEST" ALGO="$ALGO" SEED="$SEED" NUM_ITEMS="$NUM_ITEMS" MODEL="$MODEL"
else
    make sim TEST="$TEST" SEED="$SEED" NUM_ITEMS="$NUM_ITEMS"
fi
