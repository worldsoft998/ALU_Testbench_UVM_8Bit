#!/usr/bin/env bash
#===============================================================================
# AIa-VO: VCS Simulation Runner Script
# Compiles and runs ALU UVM testbench with Synopsys VCS
#
# Usage:
#   ./scripts/run_vcs.sh [options]
#
# Options:
#   --seed <value>        Random seed (default: random)
#   --num-items <value>   Number of test items (default: 5000)
#   --coverage            Enable coverage collection
#   --gui                 Launch DVE for waveform viewing
#   --verbosity <level>   UVM verbosity (UVM_LOW, UVM_MEDIUM, UVM_HIGH)
#   --compile-only        Only compile, do not run
#   --clean               Clean work directory before build
#   --work-dir <path>     Work directory (default: sim_work)
#===============================================================================

set -euo pipefail

# Default values
SEED=${SEED:-$RANDOM}
NUM_ITEMS=${NUM_ITEMS:-5000}
COVERAGE=${COVERAGE:-1}
GUI=${GUI:-0}
VERBOSITY=${VERBOSITY:-UVM_LOW}
COMPILE_ONLY=${COMPILE_ONLY:-0}
CLEAN=${CLEAN:-0}
WORK_DIR=${WORK_DIR:-sim_work}

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DUT_DIR="$PROJECT_ROOT/DUT"
TB_DIR="$PROJECT_ROOT/Testbench"

# Source files (existing testbench - NOT MODIFIED)
DUT_FILES=(
    "$DUT_DIR/ALU_DUT.sv"
    "$DUT_DIR/ALU_interface.sv"
)
TB_FILES=(
    "$TB_DIR/ALU_pkg.sv"
    "$TB_DIR/ALU_Top.sv"
)

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --seed)       SEED="$2";       shift 2 ;;
        --num-items)  NUM_ITEMS="$2";  shift 2 ;;
        --coverage)   COVERAGE=1;      shift ;;
        --no-coverage) COVERAGE=0;     shift ;;
        --gui)        GUI=1;           shift ;;
        --verbosity)  VERBOSITY="$2";  shift 2 ;;
        --compile-only) COMPILE_ONLY=1; shift ;;
        --clean)      CLEAN=1;         shift ;;
        --work-dir)   WORK_DIR="$2";   shift 2 ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

WORK_PATH="$PROJECT_ROOT/$WORK_DIR"
SIMV="$WORK_PATH/simv"

# Clean if requested
if [[ $CLEAN -eq 1 ]] && [[ -d "$WORK_PATH" ]]; then
    echo "[AIa-VO] Cleaning $WORK_PATH..."
    rm -rf "$WORK_PATH"
fi

mkdir -p "$WORK_PATH"

#--- Compile ---
echo "================================================================"
echo "[AIa-VO] Compiling design with VCS..."
echo "================================================================"

COMPILE_CMD=(
    vcs
    -full64
    -sverilog
    +acc
    -timescale=1ns/1ps
    -ntb_opts uvm-1.2
    "+incdir+$TB_DIR"
    "+incdir+$DUT_DIR"
    -o "$SIMV"
    -debug_access+all
)

if [[ $COVERAGE -eq 1 ]]; then
    COMPILE_CMD+=(
        -cm line+cond+fsm+tgl+branch+assert
        -cm_dir "$WORK_PATH/compile_coverage"
    )
fi

COMPILE_CMD+=("${DUT_FILES[@]}" "${TB_FILES[@]}")

echo "[AIa-VO] ${COMPILE_CMD[*]}"
cd "$WORK_PATH"
"${COMPILE_CMD[@]}" 2>&1 | tee "$WORK_PATH/compile.log"

if [[ $COMPILE_ONLY -eq 1 ]]; then
    echo "[AIa-VO] Compile-only mode. Done."
    exit 0
fi

#--- Run Simulation ---
echo "================================================================"
echo "[AIa-VO] Running simulation..."
echo "  Seed:       $SEED"
echo "  Num Items:  $NUM_ITEMS"
echo "  Verbosity:  $VERBOSITY"
echo "  Coverage:   $COVERAGE"
echo "================================================================"

ITER_DIR="$WORK_PATH/run_seed_${SEED}"
mkdir -p "$ITER_DIR"

RUN_CMD=(
    "$SIMV"
    "+ntb_random_seed=$SEED"
    "+UVM_TESTNAME=ALU_Test"
    "+UVM_VERBOSITY=$VERBOSITY"
    "+num_items=$NUM_ITEMS"
)

if [[ $COVERAGE -eq 1 ]]; then
    RUN_CMD+=(
        -cm line+cond+fsm+tgl+branch+assert
        -cm_dir "$ITER_DIR/coverage_db"
        -cm_name "seed_${SEED}"
    )
fi

if [[ $GUI -eq 1 ]]; then
    RUN_CMD+=(-gui)
fi

cd "$ITER_DIR"
echo "[AIa-VO] ${RUN_CMD[*]}"
"${RUN_CMD[@]}" 2>&1 | tee "$ITER_DIR/simulation.log"

echo "================================================================"
echo "[AIa-VO] Simulation complete."
echo "  Log:      $ITER_DIR/simulation.log"
if [[ $COVERAGE -eq 1 ]]; then
    echo "  Coverage: $ITER_DIR/coverage_db"
fi
echo "================================================================"
