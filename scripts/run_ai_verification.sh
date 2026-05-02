#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_ai_verification.sh — End-to-end AI-directed verification flow
#
# Orchestrates:
#   1. RL agent training  (Python model, no VCS needed)
#   2. AI-directed simulation  (VCS or Python model)
#   3. Baseline comparison
#   4. Report generation
#
# Usage:
#   ./scripts/run_ai_verification.sh [OPTIONS]
#
# Options:
#   --algorithm <alg>     RL algorithm: ppo|dqn|a2c  (default: ppo)
#   --timesteps <N>       Training timesteps          (default: 50000)
#   --iterations <N>      Max verification iterations (default: 50)
#   --target <pct>        Target coverage %           (default: 95.0)
#   --txn-per-iter <N>    Transactions per iteration  (default: 1000)
#   --seed <N>            Random seed                 (default: 42)
#   --mode <m>            python|vcs                  (default: python)
#   --output-dir <dir>    Output directory            (default: results)
#   --compare-all         Compare PPO + DQN + A2C against baseline
# ---------------------------------------------------------------------------

set -euo pipefail

ALGORITHM="ppo"
TIMESTEPS=50000
MAX_ITER=50
TARGET=95.0
TXN_PER_ITER=1000
SEED=42
MODE="python"
OUTPUT_DIR="results"
COMPARE_ALL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --algorithm)     ALGORITHM="$2";   shift 2 ;;
        --timesteps)     TIMESTEPS="$2";   shift 2 ;;
        --iterations)    MAX_ITER="$2";    shift 2 ;;
        --target)        TARGET="$2";      shift 2 ;;
        --txn-per-iter)  TXN_PER_ITER="$2"; shift 2 ;;
        --seed)          SEED="$2";        shift 2 ;;
        --mode)          MODE="$2";        shift 2 ;;
        --output-dir)    OUTPUT_DIR="$2";  shift 2 ;;
        --compare-all)   COMPARE_ALL=1;    shift   ;;
        *)               echo "Unknown option: $1"; exit 1 ;;
    esac
done

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${PROJ_ROOT}"

echo "============================================================"
echo "  AId-VO — AI-Directed Verification Optimization"
echo "============================================================"
echo "  Algorithm       : ${ALGORITHM}"
echo "  Training steps  : ${TIMESTEPS}"
echo "  Max iterations  : ${MAX_ITER}"
echo "  Target coverage : ${TARGET}%"
echo "  Txns/iteration  : ${TXN_PER_ITER}"
echo "  Seed            : ${SEED}"
echo "  Mode            : ${MODE}"
echo "  Output          : ${OUTPUT_DIR}"
echo "============================================================"

mkdir -p "${OUTPUT_DIR}"

if [[ ${COMPARE_ALL} -eq 1 ]]; then
    echo ""
    echo "[AId-VO] Running full comparison (PPO + DQN + A2C vs Baseline) ..."
    python -m ai.run_comparison \
        --algorithms ppo dqn a2c \
        --timesteps "${TIMESTEPS}" \
        --seed "${SEED}" \
        --target-coverage "${TARGET}" \
        --max-iterations "${MAX_ITER}" \
        --transactions-per-iter "${TXN_PER_ITER}" \
        --output-dir "${OUTPUT_DIR}"
else
    # Step 1: Train
    echo ""
    echo "[AId-VO] Step 1 — Training ${ALGORITHM^^} agent ..."
    python -m ai.train \
        --algorithm "${ALGORITHM}" \
        --timesteps "${TIMESTEPS}" \
        --seed "${SEED}" \
        --target-coverage "${TARGET}" \
        --max-steps "${MAX_ITER}" \
        --output-dir "${OUTPUT_DIR}"

    # Step 2: Evaluate
    echo ""
    echo "[AId-VO] Step 2 — Evaluating against baseline ..."
    python -m ai.evaluate \
        --algorithm "${ALGORITHM}" \
        --model "${OUTPUT_DIR}/models/${ALGORITHM}_model" \
        --episodes 10 \
        --seed "${SEED}" \
        --target-coverage "${TARGET}" \
        --max-steps "${MAX_ITER}" \
        --output-dir "${OUTPUT_DIR}"
fi

echo ""
echo "[AId-VO] Complete.  Results in ${OUTPUT_DIR}/"
