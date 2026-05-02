#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_vcs.sh — Run a single Synopsys VCS simulation of the ALU UVM testbench
#
# This script does NOT modify any testbench source files.  It controls
# randomisation and coverage collection purely through VCS command-line
# plusargs and compile-/run-time switches.
#
# Usage:
#   ./scripts/run_vcs.sh [OPTIONS] [+plusargs ...]
#
# Options:
#   --seed <N>        Simulation random seed (default: random)
#   --test <NAME>     UVM test name         (default: ALU_Test)
#   --log  <FILE>     Log file path         (default: logs/sim.log)
#   --verbosity <V>   UVM verbosity         (default: UVM_LOW)
#   --coverage        Enable coverage collection
#   --gui             Launch DVE waveform viewer
#   --clean           Remove previous build artifacts first
# ---------------------------------------------------------------------------

set -euo pipefail

# ── Defaults ───────────────────────────────────────────────────────────────
SEED=""
TEST="ALU_Test"
LOG_FILE="logs/sim.log"
VERBOSITY="UVM_LOW"
COVERAGE=0
GUI=0
CLEAN=0
EXTRA_PLUSARGS=()

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUT_DIR="${PROJ_ROOT}/DUT"
TB_DIR="${PROJ_ROOT}/Testbench"
WORK_DIR="${PROJ_ROOT}/work"
COV_DIR="${PROJ_ROOT}/coverage"

# ── Parse arguments ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --seed)       SEED="$2";       shift 2 ;;
        --test)       TEST="$2";       shift 2 ;;
        --log)        LOG_FILE="$2";   shift 2 ;;
        --verbosity)  VERBOSITY="$2";  shift 2 ;;
        --coverage)   COVERAGE=1;      shift   ;;
        --gui)        GUI=1;           shift   ;;
        --clean)      CLEAN=1;         shift   ;;
        +*)           EXTRA_PLUSARGS+=("$1"); shift ;;
        *)            echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Preparation ───────────────────────────────────────────────────────────
mkdir -p "${WORK_DIR}" "$(dirname "${LOG_FILE}")" "${COV_DIR}"

if [[ ${CLEAN} -eq 1 ]]; then
    echo "[run_vcs] Cleaning build artifacts ..."
    rm -rf "${WORK_DIR}/simv" "${WORK_DIR}/simv.daidir" "${WORK_DIR}/csrc"
fi

# Generate random seed if not specified
if [[ -z "${SEED}" ]]; then
    SEED=$((RANDOM * RANDOM))
fi

echo "[run_vcs] Seed=${SEED}  Test=${TEST}  Log=${LOG_FILE}"

# ── Compile ───────────────────────────────────────────────────────────────
VCS_COMPILE_OPTS=(
    -full64
    -sverilog
    +acc
    -timescale=1ns/1ps
    -ntb_opts uvm-1.2
    +incdir+"${TB_DIR}"
    +incdir+"${DUT_DIR}"
    "${DUT_DIR}/ALU_DUT.sv"
    "${DUT_DIR}/ALU_interface.sv"
    "${TB_DIR}/ALU_pkg.sv"
    "${TB_DIR}/ALU_Top.sv"
    -o "${WORK_DIR}/simv"
    -Mdir="${WORK_DIR}/csrc"
)

if [[ ${COVERAGE} -eq 1 ]]; then
    VCS_COMPILE_OPTS+=(
        -cm line+cond+fsm+branch+tgl
        -cm_dir "${COV_DIR}/compile_db"
    )
fi

echo "[run_vcs] Compiling ..."
cd "${PROJ_ROOT}"
vcs "${VCS_COMPILE_OPTS[@]}" 2>&1 | tee "${WORK_DIR}/compile.log"

# ── Run ───────────────────────────────────────────────────────────────────
SIM_OPTS=(
    +UVM_TESTNAME="${TEST}"
    +UVM_VERBOSITY="${VERBOSITY}"
    +ntb_random_seed="${SEED}"
    "${EXTRA_PLUSARGS[@]}"
)

if [[ ${COVERAGE} -eq 1 ]]; then
    SIM_OPTS+=(
        -cm line+cond+fsm+branch+tgl
        -cm_dir "${COV_DIR}/sim_db"
        -cm_log "${COV_DIR}/cm.log"
    )
fi

if [[ ${GUI} -eq 1 ]]; then
    SIM_OPTS+=(-gui)
fi

echo "[run_vcs] Running simulation ..."
"${WORK_DIR}/simv" "${SIM_OPTS[@]}" 2>&1 | tee "${LOG_FILE}"

echo "[run_vcs] Done.  Log: ${LOG_FILE}"

# ── Coverage report (if enabled) ──────────────────────────────────────────
if [[ ${COVERAGE} -eq 1 ]]; then
    echo "[run_vcs] Generating coverage report ..."
    urg -dir "${COV_DIR}/sim_db" -report "${COV_DIR}/urgReport" 2>/dev/null || true
    echo "[run_vcs] Coverage report: ${COV_DIR}/urgReport/"
fi
