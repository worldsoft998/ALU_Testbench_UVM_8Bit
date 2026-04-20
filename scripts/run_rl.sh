#!/bin/bash
# =============================================================================
# Run RL-Guided Simulation
# =============================================================================
# Usage: ./scripts/run_rl.sh [ALGORITHM] [NUM_TX] [TRAIN_STEPS] [SEED]
# =============================================================================

set -e

ALGO=${1:-PPO}
NUM_TX=${2:-1000}
TRAIN_STEPS=${3:-50000}
SEED=${4:-42}

echo "========================================"
echo " RL-Guided ALU Verification"
echo " Algorithm: $ALGO"
echo " Transactions: $NUM_TX"
echo " Training steps: $TRAIN_STEPS"
echo " Seed: $SEED"
echo "========================================"

# Step 1: Train and generate stimuli
echo ""
echo "--- Step 1: Train RL Agent & Generate Stimuli ---"
make generate RL_ALGO=$ALGO NUM_TX=$NUM_TX TRAIN_STEPS=$TRAIN_STEPS SEED=$SEED

# Step 2: Run simulation with RL stimuli
echo ""
echo "--- Step 2: Run VCS Simulation ---"
make sim_rl RL_ALGO=$ALGO NUM_TX=$NUM_TX COV=1

echo ""
echo "Simulation complete. Check logs/ for details."
echo "Coverage report: sim_work/rl_coverage_report.txt"
