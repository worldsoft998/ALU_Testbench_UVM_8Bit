#!/usr/bin/env bash
#===============================================================================
# AIa-VO: AI-Guided Verification Runner
# Launches the Python AI agent to orchestrate intelligent verification
#===============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
CONFIG_FILE=${CONFIG_FILE:-"$PROJECT_ROOT/config/default.yaml"}
LLM_PROVIDER=${LLM_PROVIDER:-"openai"}
ML_ALGORITHM=${ML_ALGORITHM:-"bayesian"}
TARGET_COVERAGE=${TARGET_COVERAGE:-100.0}
MAX_ITERATIONS=${MAX_ITERATIONS:-50}
NUM_ITEMS=${NUM_ITEMS:-5000}
COMPARISON=${COMPARISON:-1}

echo "================================================================"
echo "[AIa-VO] AI-Guided Verification Acceleration"
echo "  LLM Provider:     $LLM_PROVIDER"
echo "  ML Algorithm:     $ML_ALGORITHM"
echo "  Target Coverage:  $TARGET_COVERAGE%"
echo "  Max Iterations:   $MAX_ITERATIONS"
echo "  Comparison Mode:  $COMPARISON"
echo "================================================================"

# Validate Python environment
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found."
    exit 1
fi

# Run the AI agent
cd "$PROJECT_ROOT"
python3 -m ai_agent.cli \
    --config "$CONFIG_FILE" \
    --llm-provider "$LLM_PROVIDER" \
    --ml-algorithm "$ML_ALGORITHM" \
    --target-coverage "$TARGET_COVERAGE" \
    --max-iterations "$MAX_ITERATIONS" \
    --num-items "$NUM_ITEMS" \
    $([ "$COMPARISON" -eq 1 ] && echo "--comparison" || echo "--no-comparison")
