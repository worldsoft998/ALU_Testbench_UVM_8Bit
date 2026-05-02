#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_comparison.sh — Quick comparison: all algorithms vs baseline
# ---------------------------------------------------------------------------

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${PROJ_ROOT}"

python -m ai.run_comparison \
    --algorithms ppo dqn a2c \
    --timesteps "${1:-50000}" \
    --seed "${2:-42}" \
    --target-coverage "${3:-95.0}" \
    --max-iterations "${4:-50}" \
    --output-dir "${5:-results}" \
    "$@"
