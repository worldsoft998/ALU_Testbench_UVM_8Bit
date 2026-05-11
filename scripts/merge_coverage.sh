#!/usr/bin/env bash
#===============================================================================
# AIa-VO: Coverage Merge Utility
# Merges multiple VCS coverage databases and generates reports
#===============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR=${OUTPUT_DIR:-"$PROJECT_ROOT/results/merged_coverage"}
FORMAT=${FORMAT:-text}  # text, html, both

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <coverage_dir1> [coverage_dir2] ..."
    echo ""
    echo "Options (via environment variables):"
    echo "  OUTPUT_DIR=<path>   Output directory (default: results/merged_coverage)"
    echo "  FORMAT=text|html    Report format (default: text)"
    exit 1
fi

COVERAGE_DIRS=("$@")

echo "[AIa-VO] Merging ${#COVERAGE_DIRS[@]} coverage databases..."

mkdir -p "$OUTPUT_DIR"

URG_CMD=(
    urg
    -dir "${COVERAGE_DIRS[@]}"
    -dbname "$OUTPUT_DIR/merged_db"
    -report "$OUTPUT_DIR/report"
)

if [[ "$FORMAT" == "both" ]]; then
    URG_CMD+=(-format text -format html)
elif [[ "$FORMAT" == "html" ]]; then
    URG_CMD+=(-format html)
else
    URG_CMD+=(-format text)
fi

echo "[AIa-VO] ${URG_CMD[*]}"
"${URG_CMD[@]}" 2>&1 | tee "$OUTPUT_DIR/merge.log"

echo "[AIa-VO] Coverage merge complete."
echo "  Report: $OUTPUT_DIR/report"
echo "  Database: $OUTPUT_DIR/merged_db"
