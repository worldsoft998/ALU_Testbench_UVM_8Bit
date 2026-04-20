#!/bin/bash
# =============================================================================
# Run Baseline Random Simulation
# =============================================================================
# Usage: ./scripts/run_random.sh [NUM_TX] [SEED]
# =============================================================================

set -e

NUM_TX=${1:-80000}
SEED=${2:-42}
VERBOSITY=${3:-UVM_LOW}

echo "========================================"
echo " Baseline Random Simulation"
echo " Transactions: $NUM_TX"
echo " Seed: $SEED"
echo "========================================"

make sim NUM_TX=$NUM_TX SEED=$SEED VERBOSITY=$VERBOSITY COV=1

echo ""
echo "Simulation complete. Check logs/sim_baseline.log for details."
