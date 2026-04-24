#!/bin/bash
#
# ALU Verification Simulation Runner
# Supports both baseline (no AI) and AI-assisted modes
#
# Usage:
#   ./run_simulation.sh [OPTIONS]
#
# Options:
#   --use-ai          Enable AI-assisted stimulus generation
#   --algorithm NAME  RL algorithm to use (ppo, a2c, dqn, sac, td3, random)
#   --transactions N  Number of transactions to simulate
#   --coverage TARGET Coverage target (0.0-1.0)
#   --python-host IP  Python RL server host
#   --python-port N   Python RL server port
#   --compare         Run comparison between baseline and AI
#   --help            Show this help message
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
USE_AI=0
ALGORITHM="ppo"
NUM_TRANSACTIONS=100000
COVERAGE_TARGET=0.95
PYTHON_HOST="localhost"
PYTHON_PORT=5555
COMPARE=0
VERBOSE=1

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
RESULTS_DIR="$PROJECT_ROOT/results"

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --use-ai)
                USE_AI=1
                shift
                ;;
            --algorithm)
                ALGORITHM="$2"
                shift 2
                ;;
            --transactions)
                NUM_TRANSACTIONS="$2"
                shift 2
                ;;
            --coverage)
                COVERAGE_TARGET="$2"
                shift 2
                ;;
            --python-host)
                PYTHON_HOST="$2"
                shift 2
                ;;
            --python-port)
                PYTHON_PORT="$2"
                shift 2
                ;;
            --compare)
                COMPARE=1
                shift
                ;;
            --quiet)
                VERBOSE=0
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    echo "ALU Verification Simulation Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --use-ai              Enable AI-assisted stimulus generation"
    echo "  --algorithm NAME      RL algorithm (ppo, a2c, dqn, sac, td3, random) [default: ppo]"
    echo "  --transactions N      Number of transactions [default: 100000]"
    echo "  --coverage TARGET     Coverage target 0.0-1.0 [default: 0.95]"
    echo "  --python-host IP      Python RL server host [default: localhost]"
    echo "  --python-port N       Python RL server port [default: 5555]"
    echo "  --compare             Run comparison between baseline and AI"
    echo "  --quiet               Suppress verbose output"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run baseline simulation"
    echo "  $0 --use-ai --algorithm ppo           # Run with PPO agent"
    echo "  $0 --use-ai --transactions 50000      # Run with fewer transactions"
    echo "  $0 --compare                          # Compare baseline vs AI"
}

# Setup directories
setup() {
    mkdir -p "$LOG_DIR" "$RESULTS_DIR"
}

# Print status
print_status() {
    if [ $VERBOSE -eq 1 ]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

print_success() {
    if [ $VERBOSE -eq 1 ]; then
        echo -e "${GREEN}[OK]${NC} $1"
    fi
}

print_warning() {
    if [ $VERBOSE -eq 1 ]; then
        echo -e "${YELLOW}[WARN]${NC} $1"
    fi
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Start Python RL server
start_python_server() {
    print_status "Starting Python RL server..."
    
    cd "$PROJECT_ROOT/Python"
    
    # Check if server script exists
    if [ ! -f "start_rl_server.py" ]; then
        print_warning "Python RL server script not found"
        return 1
    fi
    
    # Start server in background
    python3 start_rl_server.py \
        --host "$PYTHON_HOST" \
        --port "$PYTHON_PORT" \
        --algorithm "$ALGORITHM" > "$LOG_DIR/rl_server.log" 2>&1 &
    
    SERVER_PID=$!
    print_success "Python RL server started (PID: $SERVER_PID)"
    
    # Wait for server to start
    sleep 2
    
    return 0
}

# Stop Python RL server
stop_python_server() {
    if [ -n "$SERVER_PID" ]; then
        print_status "Stopping Python RL server..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
        print_success "Python RL server stopped"
    fi
}

# Run baseline simulation
run_baseline() {
    print_status "Running baseline simulation..."
    
    cd "$PROJECT_ROOT"
    
    make simulate \
        USE_AI=0 \
        NUM_TRANSACTIONS="$NUM_TRANSACTIONS" \
        COVERAGE_TARGET="$COVERAGE_TARGET" \
        2>&1 | tee "$LOG_DIR/baseline_simulation.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Baseline simulation completed"
    else
        print_error "Baseline simulation failed"
        return 1
    fi
}

# Run AI-assisted simulation
run_ai_simulation() {
    print_status "Running AI-assisted simulation ($ALGORITHM)..."
    
    cd "$PROJECT_ROOT"
    
    make simulate \
        USE_AI=1 \
        ALGORITHM="$ALGORITHM" \
        NUM_TRANSACTIONS="$NUM_TRANSACTIONS" \
        COVERAGE_TARGET="$COVERAGE_TARGET" \
        PYTHON_HOST="$PYTHON_HOST" \
        PYTHON_PORT="$PYTHON_PORT" \
        2>&1 | tee "$LOG_DIR/ai_simulation.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "AI-assisted simulation completed"
    else
        print_error "AI-assisted simulation failed"
        return 1
    fi
}

# Run comparison
run_comparison() {
    print_status "Running baseline vs AI comparison..."
    
    # Create comparison report
    python3 "$PROJECT_ROOT/Python/Analysis/comparison_report.py" \
        --baseline "$RESULTS_DIR/baseline_results.json" \
        --ai "$RESULTS_DIR/ai_results.json" \
        --output "$RESULTS_DIR/comparison_report.txt"
    
    print_success "Comparison report generated: $RESULTS_DIR/comparison_report.txt"
}

# Main function
main() {
    parse_args "$@"
    setup
    
    echo "=============================================="
    echo "  ALU Verification Simulation Runner"
    echo "=============================================="
    echo ""
    
    if [ $COMPARE -eq 1 ]; then
        # Run comparison
        print_status "Mode: BASELINE vs AI COMPARISON"
        echo ""
        
        run_baseline || exit 1
        echo ""
        
        start_python_server || true
        run_ai_simulation || true
        stop_python_server
        echo ""
        
        run_comparison
        
    elif [ $USE_AI -eq 1 ]; then
        # Run AI-assisted only
        print_status "Mode: AI-ASSISTED ($ALGORITHM)"
        echo ""
        
        start_python_server || true
        run_ai_simulation
        stop_python_server
        
    else
        # Run baseline only
        print_status "Mode: BASELINE (No AI)"
        echo ""
        
        run_baseline
    fi
    
    echo ""
    echo "=============================================="
    echo "  Simulation Complete"
    echo "=============================================="
    echo ""
    echo "Results saved to: $RESULTS_DIR"
    echo "Logs saved to: $LOG_DIR"
}

# Run main
main "$@"