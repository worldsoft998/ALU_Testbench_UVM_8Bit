#!/usr/bin/env bash
#===============================================================================
# AIa-VO: Baseline (Non-AI) Regression Runner
# Runs multiple simulations with fixed random seeds for comparison
#===============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

NUM_RUNS=${NUM_RUNS:-10}
NUM_ITEMS=${NUM_ITEMS:-5000}
WORK_DIR=${WORK_DIR:-sim_work/baseline}

# Fixed baseline seeds (deterministic for reproducible comparison)
BASELINE_SEEDS=(12345 54321 98765 11111 22222 33333 44444 55555 66666 77777
                88888 99999 13579 24680 31415 27182 14142 17320 22360 26457)

echo "================================================================"
echo "[AIa-VO] Baseline Regression (No AI)"
echo "  Runs:       $NUM_RUNS"
echo "  Num Items:  $NUM_ITEMS"
echo "================================================================"

# Compile once
"$SCRIPT_DIR/run_vcs.sh" --compile-only --work-dir "$WORK_DIR" --clean

COVERAGE_DIRS=()

for ((i=0; i<NUM_RUNS; i++)); do
    SEED=${BASELINE_SEEDS[$i]}
    echo ""
    echo "[Baseline Run $((i+1))/$NUM_RUNS] Seed=$SEED"

    WORK_DIR_ABS="$PROJECT_ROOT/$WORK_DIR"
    ITER_DIR="$WORK_DIR_ABS/run_baseline_${i}_seed_${SEED}"
    mkdir -p "$ITER_DIR"

    SIMV="$WORK_DIR_ABS/simv"
    cd "$ITER_DIR"

    "$SIMV" \
        "+ntb_random_seed=$SEED" \
        "+UVM_TESTNAME=ALU_Test" \
        "+UVM_VERBOSITY=UVM_LOW" \
        "+num_items=$NUM_ITEMS" \
        -cm line+cond+fsm+tgl+branch+assert \
        -cm_dir "$ITER_DIR/coverage_db" \
        -cm_name "baseline_seed_${SEED}" \
        2>&1 | tee "$ITER_DIR/simulation.log"

    COVERAGE_DIRS+=("$ITER_DIR/coverage_db")
done

# Merge coverage
echo ""
echo "================================================================"
echo "[AIa-VO] Merging baseline coverage..."
echo "================================================================"

MERGED_DIR="$PROJECT_ROOT/$WORK_DIR/merged_coverage"
mkdir -p "$MERGED_DIR"

if command -v urg &>/dev/null; then
    urg \
        -dir "${COVERAGE_DIRS[@]}" \
        -dbname "$MERGED_DIR/merged_db" \
        -report "$MERGED_DIR/report" \
        -format text \
        2>&1 | tee "$MERGED_DIR/urg.log"
    echo "[AIa-VO] Merged coverage report: $MERGED_DIR/report"
else
    echo "[AIa-VO] Warning: URG not found. Coverage merge skipped."
fi

echo ""
echo "================================================================"
echo "[AIa-VO] Baseline regression complete."
echo "  Results: $PROJECT_ROOT/$WORK_DIR"
echo "================================================================"
