#!/bin/bash
# =============================================================================
# Run RL vs Random Comparison
# =============================================================================
# Usage: ./scripts/compare.sh [ALGORITHM] [TRAIN_STEPS] [NUM_TX] [EPISODES]
# =============================================================================

set -e

ALGO=${1:-PPO}
TRAIN_STEPS=${2:-50000}
NUM_TX=${3:-5000}
EPISODES=${4:-10}
SEED=${5:-42}

echo "========================================"
echo " RL vs Random Comparison"
echo " Algorithm: $ALGO"
echo " Training steps: $TRAIN_STEPS"
echo " Max transactions: $NUM_TX"
echo " Episodes: $EPISODES"
echo "========================================"

make compare \
    RL_ALGO=$ALGO \
    TRAIN_STEPS=$TRAIN_STEPS \
    NUM_TX=$NUM_TX \
    SEED=$SEED

echo ""
echo "Results saved to results/"
echo "  - results/comparison_report.txt"
echo "  - results/comparison_results.json"
echo "  - results/coverage_trajectories.csv"
if [ -f results/coverage_comparison.png ]; then
    echo "  - results/coverage_comparison.png"
fi
