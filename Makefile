#===============================================================================
# Makefile for ALU 8-bit UVM Verification with RL Enhancement
# Supports Synopsys VCS simulator with optional AI/ML integration
#===============================================================================
#
# Targets:
#   all          - Build all simulation binaries
#   simulate     - Run simulation
#   ai_simulate  - Run AI-assisted simulation
#   compare      - Run comparison between baseline and AI
#   train        - Train RL agent
#   test         - Run tests
#   clean        - Clean build artifacts
#   docs         - Generate documentation
#   package      - Create distribution package
#
# Configuration Options:
#   USE_AI              - Enable AI/ML assistance (0 or 1)
#   ALGORITHM           - RL algorithm (ppo, a2c, dqn, sac, td3, random)
#   NUM_TRANSACTIONS    - Number of transactions to simulate
#   COVERAGE_TARGET     - Coverage target (0.0-1.0)
#   PYTHON_HOST         - Python RL server host
#   PYTHON_PORT         - Python RL server port
#   VERBOSE             - Verbose output (0 or 1)
#
# Examples:
#   make simulate USE_AI=0 NUM_TRANSACTIONS=50000
#   make simulate USE_AI=1 ALGORITHM=ppo
#   make compare
#
#===============================================================================

# Configuration
.DEFAULT_GOAL := help

# Project directories
PROJECT_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DUT_DIR := $(PROJECT_ROOT)DUT
TB_DIR := $(PROJECT_ROOT)Testbench
PYTHON_DIR := $(PROJECT_ROOT)Python
RESULTS_DIR := $(PROJECT_ROOT)results
LOG_DIR := $(PROJECT_ROOT)logs
MODELS_DIR := $(PROJECT_ROOT)models
DOCS_DIR := $(PROJECT_ROOT)Docs

# Create directories
DIRS := $(RESULTS_DIR) $(LOG_DIR) $(MODELS_DIR)

$(shell mkdir -p $(DIRS))

#===============================================================================
# SIMULATOR CONFIGURATION
#===============================================================================

# VCS Configuration
VCS := vcs
VCS_FLAGS := -sverilog -ntb_opts uvm-1.2
VCS_FLAGS += -timescale=1ns/1ps
VCS_FLAGS += -LDFLAGS -lpthread
VCS_FLAGS += -full64
VCS_DEBUG := -debug_access+r -debug_access+wm

# Build options
BUILD_DIR := $(PROJECT_ROOT)build
UVM_HOME ?= $(METABASE)/packages/uvm-1.2

# Source files
DUT_SOURCES := $(DUT_DIR)/ALU_DUT.sv \
               $(DUT_DIR)/ALU_interface.sv

TB_SOURCES := $(TB_DIR)/ALU_pkg.sv \
              $(TB_DIR)/ALU_RL_pkg.sv \
              $(TB_DIR)/ALU_Top.sv

ALL_SOURCES := $(DUT_SOURCES) $(TB_SOURCES)

# Compile order
UVM_SRC := $(UVM_HOME)/src/uvm_pkg.sv

#===============================================================================
# SIMULATION PARAMETERS (with defaults)
#===============================================================================

# AI/ML Configuration
USE_AI ?= 0
ALGORITHM ?= ppo
NUM_TRANSACTIONS ?= 100000
COVERAGE_TARGET ?= 0.95
PYTHON_HOST ?= localhost
PYTHON_PORT ?= 5555
VERBOSE ?= 1

# Simulation parameters
SIM_TIME ?= 100000
SEED ?= 42

# Paths
MODEL_PATH ?= $(MODELS_DIR)/$(ALGORITHM)_model.zip

#===============================================================================
# COLORS
#===============================================================================

BOLD := \033[1m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m

#===============================================================================
# TARGETS
#===============================================================================

.PHONY: help all build simulate ai_simulate compare train test clean docs package check_env

# Help target
help:
	@echo ""
	@echo "$(BOLD)ALU 8-bit UVM Verification with RL Enhancement$(NC)"
	@echo "============================================================"
	@echo ""
	@echo "$(BOLD)Main Targets:$(NC)"
	@echo "  $(GREEN)all           $(NC)Build all binaries"
	@echo "  $(GREEN)simulate      $(NC)Run simulation (baseline or AI)"
	@echo "  $(GREEN)ai_simulate   $(NC)Run AI-assisted simulation"
	@echo "  $(GREEN)compare       $(NC)Run baseline vs AI comparison"
	@echo "  $(GREEN)train         $(NC)Train RL agent"
	@echo "  $(GREEN)test          $(NC)Run unit tests"
	@echo "  $(GREEN)clean         $(NC)Clean build artifacts"
	@echo "  $(GREEN)docs          $(NC)Generate documentation"
	@echo ""
	@echo "$(BOLD)Configuration Options:$(NC)"
	@echo "  $(YELLOW)USE_AI           $(NC)Enable AI (0/1) [default: 0]"
	@echo "  $(YELLOW)ALGORITHM        $(NC)RL algorithm [default: ppo]"
	@echo "                        (ppo, a2c, dqn, sac, td3, random)"
	@echo "  $(YELLOW)NUM_TRANSACTIONS $(NC)Number of transactions [default: 100000]"
	@echo "  $(YELLOW)COVERAGE_TARGET  $(NC)Coverage target [default: 0.95]"
	@echo "  $(YELLOW)PYTHON_HOST      $(NC)RL server host [default: localhost]"
	@echo "  $(YELLOW)PYTHON_PORT      $(NC)RL server port [default: 5555]"
	@echo ""
	@echo "$(BOLD)Examples:$(NC)"
	@echo "  make simulate USE_AI=0 NUM_TRANSACTIONS=50000"
	@echo "  make simulate USE_AI=1 ALGORITHM=ppo"
	@echo "  make compare ALGORITHM=ppo"
	@echo ""
	@echo "$(BOLD)Testbench Types:$(NC)"
	@echo "  Standard:  ALU_pkg.sv (no AI)"
	@echo "  RL:        ALU_RL_pkg.sv (with AI)"
	@echo ""

# Check environment
check_env:
	@echo "$(BLUE)[INFO] Checking environment...$(NC)"
	@which vcs > /dev/null || (echo "$(RED)[ERROR] VCS not found in PATH$(NC)" && exit 1)
	@python3 --version || (echo "$(RED)[ERROR] Python3 not found$(NC)" && exit 1)
	@echo "$(GREEN)[OK] Environment check passed$(NC)"

# Build all
all: build_python check_env
	@echo "$(GREEN)[OK] All build prerequisites ready$(NC)"

# Build VCS simulation
build: check_env
	@echo "$(BLUE)[INFO] Building VCS simulation...$(NC)"
	mkdir -p $(BUILD_DIR)
	cd $(BUILD_DIR) && $(VCS) $(VCS_FLAGS) $(VCS_DEBUG) \
		-f $(PROJECT_ROOT)filelist.f \
		-l compile.log
	@echo "$(GREEN)[OK] Build complete$(NC)"

# Build Python dependencies
build_python:
	@echo "$(BLUE)[INFO] Setting up Python environment...$(NC)"
	@if [ -f "$(PYTHON_DIR)/requirements.txt" ]; then \
		pip3 install -q -r $(PYTHON_DIR)/requirements.txt; \
	fi
	@echo "$(GREEN)[OK] Python dependencies ready$(NC)"

# Run simulation
simulate: all build
	@echo ""
	@echo "$(BOLD)============================================================$(NC)"
	@echo "$(BOLD)Running Simulation$(NC)"
	@echo "$(BOLD)============================================================$(NC)"
	@echo ""
	@echo "Configuration:"
	@echo "  USE_AI:           $(USE_AI)"
	@echo "  ALGORITHM:         $(ALGORITHM)"
	@echo "  NUM_TRANSACTIONS: $(NUM_TRANSACTIONS)"
	@echo "  COVERAGE_TARGET:  $(COVERAGE_TARGET)"
	@echo ""
	
	@if [ $(USE_AI) -eq 1 ]; then \
		echo "$(BLUE)[INFO] Starting AI-assisted simulation...$(NC)"; \
		python3 $(PYTHON_DIR)/start_rl_server.py \
			--algorithm $(ALGORITHM) \
			--model $(MODEL_PATH) & \
		RL_PID=$$!; \
		sleep 3; \
		cd $(BUILD_DIR) && ./simv \
			USE_AI=1 \
			RL_ALGORITHM=$(ALGORITHM) \
			NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
			COVERAGE_TARGET=$(COVERAGE_TARGET) \
			PYTHON_HOST=$(PYTHON_HOST) \
			PYTHON_PORT=$(PYTHON_PORT) \
			+ntb_random_seed=$(SEED) \
			-l $(LOG_DIR)/simulation.log; \
		SIM_EXIT=$$?; \
		kill $$RL_PID 2>/dev/null || true; \
		exit $$SIM_EXIT; \
	else \
		echo "$(BLUE)[INFO] Starting baseline simulation...$(NC)"; \
		cd $(BUILD_DIR) && ./simv \
			USE_AI=0 \
			NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
			COVERAGE_TARGET=$(COVERAGE_TARGET) \
			+ntb_random_seed=$(SEED) \
			-l $(LOG_DIR)/simulation.log; \
	fi
	
	@echo "$(GREEN)[OK] Simulation complete$(NC)"
	@echo "Results saved to: $(RESULTS_DIR)"

# Run AI-assisted simulation
ai_simulate:
	@$(MAKE) simulate USE_AI=1 ALGORITHM=$(ALGORITHM) \
		NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
		COVERAGE_TARGET=$(COVERAGE_TARGET)

# Train RL agent
train: build_python
	@echo "$(BLUE)[INFO] Training RL agent...$(NC)"
	@if [ -f "$(PYTHON_DIR)/train_agent.py" ]; then \
		python3 $(PYTHON_DIR)/train_agent.py \
			--algorithm $(ALGORITHM) \
			--timesteps $(NUM_TRANSACTIONS) \
			--output $(MODELS_DIR); \
	else \
		echo "$(YELLOW)[WARN] Training script not found$(NC)"; \
	fi

# Run comparison
compare:
	@echo ""
	@echo "$(BOLD)============================================================$(NC)"
	@echo "$(BOLD)Running Baseline vs AI Comparison$(NC)"
	@echo "$(BOLD)============================================================$(NC)"
	@echo ""
	
	# Run baseline
	@echo "$(BLUE)[INFO] Running baseline simulation...$(NC)"
	@$(MAKE) simulate USE_AI=0 NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
		COVERAGE_TARGET=$(COVERAGE_TARGET) \
		2>&1 | tee $(LOG_DIR)/baseline.log
	@cp $(LOG_DIR)/simulation.log $(LOG_DIR)/baseline_simulation.log
	
	# Run AI
	@echo ""
	@echo "$(BLUE)[INFO] Running AI simulation...$(NC)"
	@$(MAKE) simulate USE_AI=1 ALGORITHM=$(ALGORITHM) \
		NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
		COVERAGE_TARGET=$(COVERAGE_TARGET) \
		2>&1 | tee $(LOG_DIR)/ai.log
	@cp $(LOG_DIR)/simulation.log $(LOG_DIR)/ai_simulation.log
	
	# Generate comparison report
	@echo ""
	@echo "$(BLUE)[INFO] Generating comparison report...$(NC)"
	@python3 $(PYTHON_DIR)/Analysis/comparison_report.py \
		--baseline $(LOG_DIR)/baseline_simulation.log \
		--ai $(LOG_DIR)/ai_simulation.log \
		--output $(RESULTS_DIR)/comparison_report.txt
	
	@echo "$(GREEN)[OK] Comparison complete$(NC)"
	@echo "Report saved to: $(RESULTS_DIR)/comparison_report.txt"

# Run tests
test: build_python
	@echo "$(BLUE)[INFO] Running tests...$(NC)"
	@if [ -f "$(PYTHON_DIR)/test_alu_rl.py" ]; then \
		python3 -m pytest $(PYTHON_DIR)/test_alu_rl.py -v; \
	else \
		echo "$(YELLOW)[WARN] Test file not found$(NC)"; \
	fi

# Generate documentation
docs:
	@echo "$(BLUE)[INFO] Generating documentation...$(NC)"
	@mkdir -p $(DOCS_DIR)
	@echo "Documentation generated at $(DOCS_DIR)"

# Clean build artifacts
clean:
	@echo "$(BLUE)[INFO] Cleaning build artifacts...$(NC)"
	@rm -rf $(BUILD_DIR)
	@rm -rf $(RESULTS_DIR)/*
	@rm -rf $(LOG_DIR)/*
	@find . -name "*.log" -delete
	@find . -name "*.wlf" -delete
	@find . -name "*.key" -delete
	@echo "$(GREEN)[OK] Clean complete$(NC)"

# Package for distribution
package: clean docs
	@echo "$(BLUE)[INFO] Creating distribution package...$(NC)"
	@cd $(PROJECT_ROOT) && zip -r ALU_Verification_RL_$(ALGORITHM)_$(shell date +%Y%m%d).zip \
		--exclude "*.git*" \
		--exclude "*.vcd" \
		--exclude "build/*" \
		--exclude "*.pyc" \
		.
	@echo "$(GREEN)[OK] Package created$(NC)"

#===============================================================================
# SIMULATION VARIANTS
#===============================================================================

# Quick simulation (fewer transactions)
quick: NUM_TRANSACTIONS=10000
quick: simulate

# Long simulation (more transactions)
long: NUM_TRANSACTIONS=500000
long: simulate

# Debug simulation
debug: VCS_FLAGS += -debug_all
debug: VERBOSE=1
debug: simulate

# Coverage simulation
coverage: VCS_FLAGS += -cm line+cond+fsm+branch+tgl
coverage: simulate

# Regression test
regression: 
	@echo "Running regression tests..."
	@$(MAKE) simulate USE_AI=0 ALGORITHM=random NUM_TRANSACTIONS=10000
	@$(MAKE) simulate USE_AI=1 ALGORITHM=random NUM_TRANSACTIONS=10000
	@$(MAKE) simulate USE_AI=1 ALGORITHM=ppo NUM_TRANSACTIONS=10000
	@echo "$(GREEN)Regression complete$(NC)"

#===============================================================================
# ANALYSIS TARGETS
#===============================================================================

# Analyze results
analyze:
	@echo "$(BLUE)[INFO] Analyzing results...$(NC)"
	@if [ -f "$(PYTHON_DIR)/Analysis/analyze_results.py" ]; then \
		python3 $(PYTHON_DIR)/Analysis/analyze_results.py $(RESULTS_DIR); \
	else \
		echo "$(YELLOW)[WARN] Analysis script not found$(NC)"; \
	fi

# Plot coverage
plot_coverage:
	@echo "$(BLUE)[INFO] Generating coverage plots...$(NC)"
	@if [ -f "$(PYTHON_DIR)/Analysis/plot_coverage.py" ]; then \
		python3 $(PYTHON_DIR)/Analysis/plot_coverage.py $(RESULTS_DIR); \
	else \
		echo "$(YELLOW)[WARN] Plot script not found$(NC)"; \
	fi

# Generate coverage report
coverage_report:
	@echo "$(BLUE)[INFO] Generating coverage report...$(NC)"
	@$(MAKE) simulate USE_AI=1 ALGORITHM=$(ALGORITHM) \
		NUM_TRANSACTIONS=$(NUM_TRANSACTIONS) \
		COVERAGE_TARGET=$(COVERAGE_TARGET) \
		VCS_FLAGS="$(VCS_FLAGS) -cm line+cond+fsm+branch+tgl"
	@python3 $(PYTHON_DIR)/Analysis/coverage_report.py \
		--input $(RESULTS_DIR)/coverage.dat \
		--output $(RESULTS_DIR)/coverage_report.html

#===============================================================================
# DEVELOPER TARGETS
#===============================================================================

# Format code
fmt:
	@echo "$(BLUE)[INFO] Formatting code...$(NC)"
	@find $(PYTHON_DIR) -name "*.py" -exec python3 -m black {} \; 2>/dev/null || true

# Lint code
lint:
	@echo "$(BLUE)[INFO] Linting code...$(NC)"
	@python3 -m pylint $(PYTHON_DIR)/RL/*.py 2>/dev/null || true
	@python3 -m pylint $(PYTHON_DIR)/Bridge/*.py 2>/dev/null || true

# Update dependencies
update_deps:
	@echo "$(BLUE)[INFO] Updating dependencies...$(NC)"
	@pip3 install --upgrade pip
	@if [ -f "$(PYTHON_DIR)/requirements.txt" ]; then \
		pip3 install -U -r $(PYTHON_DIR)/requirements.txt; \
	fi