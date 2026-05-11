#===============================================================================
# AIa-VO: AI Agent Supported Verification Optimization
# Makefile for 8-Bit ALU UVM Testbench with AI-Guided Verification
#===============================================================================
#
# Usage Examples:
#   make sim                          # Run single VCS simulation (random seed)
#   make sim SEED=42 NUM_ITEMS=10000  # Run with specific seed and count
#   make ai                           # Run AI-guided verification
#   make ai ML_ALGO=rl LLM=claude     # AI with RL algorithm and Claude LLM
#   make baseline                     # Run baseline (non-AI) regression
#   make compare                      # Run AI + baseline and compare
#   make report                       # Generate comparison report only
#   make py-smoke                     # Run Python unit tests
#   make clean                        # Clean all generated files
#   make help                         # Show all targets
#
#===============================================================================

#--- Configurable Parameters ---
SEED          ?= $(shell echo $$RANDOM)
NUM_ITEMS     ?= 5000
VERBOSITY     ?= UVM_LOW
COVERAGE      ?= 1
GUI           ?= 0
WORK_DIR      ?= sim_work

# AI Configuration
LLM           ?= openai
ML_ALGO       ?= bayesian
TARGET_COV    ?= 100.0
MAX_ITER      ?= 50
COMPARISON    ?= 1
CONFIG_FILE   ?= config/default.yaml

# Baseline Configuration
BASELINE_RUNS ?= 10

# Tool paths (override if VCS is in non-standard location)
VCS           ?= vcs
URG           ?= urg
PYTHON        ?= python3

#--- Project Paths ---
PROJECT_ROOT  := $(shell pwd)
DUT_DIR       := $(PROJECT_ROOT)/DUT
TB_DIR        := $(PROJECT_ROOT)/Testbench
SCRIPTS_DIR   := $(PROJECT_ROOT)/scripts
RESULTS_DIR   := $(PROJECT_ROOT)/results
WORK_PATH     := $(PROJECT_ROOT)/$(WORK_DIR)
SIMV          := $(WORK_PATH)/simv

#--- Source Files (EXISTING TESTBENCH - NOT MODIFIED) ---
DUT_FILES     := $(DUT_DIR)/ALU_DUT.sv $(DUT_DIR)/ALU_interface.sv
TB_FILES      := $(TB_DIR)/ALU_pkg.sv $(TB_DIR)/ALU_Top.sv

#--- VCS Compile Flags ---
VCS_FLAGS     := -full64 -sverilog +acc \
                 -timescale=1ns/1ps \
                 -ntb_opts uvm-1.2 \
                 +incdir+$(TB_DIR) \
                 +incdir+$(DUT_DIR) \
                 -debug_access+all
ifeq ($(COVERAGE),1)
VCS_FLAGS     += -cm line+cond+fsm+tgl+branch+assert \
                 -cm_dir $(WORK_PATH)/compile_coverage
endif

#--- VCS Runtime Flags ---
RUN_FLAGS     := +ntb_random_seed=$(SEED) \
                 +UVM_TESTNAME=ALU_Test \
                 +UVM_VERBOSITY=$(VERBOSITY) \
                 +num_items=$(NUM_ITEMS)
ifeq ($(COVERAGE),1)
RUN_FLAGS     += -cm line+cond+fsm+tgl+branch+assert \
                 -cm_dir $(WORK_PATH)/run_seed_$(SEED)/coverage_db \
                 -cm_name seed_$(SEED)
endif
ifeq ($(GUI),1)
RUN_FLAGS     += -gui
endif

#===============================================================================
# Targets
#===============================================================================

.PHONY: help compile sim ai baseline compare report py-smoke test clean \
        clean-results clean-all zip install-deps

## Show help
help:
	@echo "==============================================================================="
	@echo "AIa-VO: AI Agent Supported Verification Optimization"
	@echo "==============================================================================="
	@echo ""
	@echo "Simulation Targets:"
	@echo "  make compile              Compile design with VCS"
	@echo "  make sim                  Run single simulation"
	@echo "  make sim SEED=42          Run simulation with specific seed"
	@echo "  make sim NUM_ITEMS=80000  Run with custom transaction count"
	@echo "  make sim GUI=1            Run with DVE waveform viewer"
	@echo ""
	@echo "AI-Guided Verification:"
	@echo "  make ai                   Run AI-guided verification (default config)"
	@echo "  make ai LLM=openai        Use OpenAI GPT as LLM provider"
	@echo "  make ai LLM=gemini        Use Google Gemini as LLM provider"
	@echo "  make ai LLM=claude        Use Anthropic Claude as LLM provider"
	@echo "  make ai ML_ALGO=bayesian  Use Bayesian optimization"
	@echo "  make ai ML_ALGO=rl        Use Reinforcement Learning"
	@echo "  make ai ML_ALGO=rf        Use Random Forest predictor"
	@echo "  make ai ML_ALGO=ensemble  Use ensemble of all ML methods"
	@echo ""
	@echo "Comparison & Analysis:"
	@echo "  make baseline             Run baseline regression (no AI)"
	@echo "  make compare              Run AI + baseline and compare"
	@echo "  make report               Generate reports from results"
	@echo ""
	@echo "Testing & Maintenance:"
	@echo "  make py-smoke             Run Python unit tests"
	@echo "  make test                 Alias for py-smoke"
	@echo "  make install-deps         Install Python dependencies"
	@echo "  make clean                Clean simulation work directory"
	@echo "  make clean-results        Clean results directory"
	@echo "  make clean-all            Clean everything"
	@echo "  make zip                  Create zip archive of project"
	@echo ""
	@echo "Configuration Variables:"
	@echo "  SEED=<int>                Random seed (default: random)"
	@echo "  NUM_ITEMS=<int>           Transactions per run (default: 5000)"
	@echo "  VERBOSITY=<level>         UVM verbosity level (default: UVM_LOW)"
	@echo "  COVERAGE=0|1              Enable coverage (default: 1)"
	@echo "  GUI=0|1                   Launch DVE GUI (default: 0)"
	@echo "  LLM=openai|gemini|claude  LLM provider (default: openai)"
	@echo "  ML_ALGO=bayesian|rl|rf|ensemble  ML algorithm (default: bayesian)"
	@echo "  TARGET_COV=<float>        Target coverage % (default: 100.0)"
	@echo "  MAX_ITER=<int>            Max AI iterations (default: 50)"
	@echo "  BASELINE_RUNS=<int>       Baseline run count (default: 10)"
	@echo "  CONFIG_FILE=<path>        YAML config file path"
	@echo "==============================================================================="

## Install Python dependencies
install-deps:
	@echo "[AIa-VO] Installing Python dependencies..."
	$(PYTHON) -m pip install -r requirements.txt

## Compile design with VCS
compile: $(SIMV)

$(SIMV): $(DUT_FILES) $(TB_FILES)
	@echo "[AIa-VO] Compiling design..."
	@mkdir -p $(WORK_PATH)
	cd $(WORK_PATH) && $(VCS) $(VCS_FLAGS) -o $(SIMV) $(DUT_FILES) $(TB_FILES) \
		2>&1 | tee $(WORK_PATH)/compile.log
	@echo "[AIa-VO] Compilation complete."

## Run single VCS simulation
sim: $(SIMV)
	@echo "[AIa-VO] Running simulation (seed=$(SEED), items=$(NUM_ITEMS))..."
	@mkdir -p $(WORK_PATH)/run_seed_$(SEED)
	cd $(WORK_PATH)/run_seed_$(SEED) && $(SIMV) $(RUN_FLAGS) \
		2>&1 | tee $(WORK_PATH)/run_seed_$(SEED)/simulation.log
	@echo "[AIa-VO] Simulation complete. Log: $(WORK_PATH)/run_seed_$(SEED)/simulation.log"

## Run AI-guided verification
ai:
	@echo "[AIa-VO] Starting AI-guided verification..."
	LLM_PROVIDER=$(LLM) ML_ALGORITHM=$(ML_ALGO) \
	TARGET_COVERAGE=$(TARGET_COV) MAX_ITERATIONS=$(MAX_ITER) \
	NUM_ITEMS=$(NUM_ITEMS) COMPARISON=$(COMPARISON) \
	CONFIG_FILE=$(CONFIG_FILE) \
		$(SCRIPTS_DIR)/run_ai_guided.sh

## Run baseline regression (no AI)
baseline:
	@echo "[AIa-VO] Starting baseline regression..."
	NUM_RUNS=$(BASELINE_RUNS) NUM_ITEMS=$(NUM_ITEMS) \
		$(SCRIPTS_DIR)/run_baseline.sh

## Run comparison (AI vs baseline)
compare:
	@echo "[AIa-VO] Running comparison..."
	$(MAKE) ai COMPARISON=1

## Generate reports from existing results
report:
	@echo "[AIa-VO] Generating reports..."
	$(PYTHON) -m ai_agent.cli --report-only --config $(CONFIG_FILE)

## Run Python smoke tests
py-smoke:
	@echo "[AIa-VO] Running Python tests..."
	$(PYTHON) -m pytest tests/ -v --tb=short 2>&1 || $(PYTHON) tests/test_rl_stack.py

## Alias for py-smoke
test: py-smoke

## Clean simulation work directory
clean:
	@echo "[AIa-VO] Cleaning work directory..."
	rm -rf $(WORK_PATH)
	rm -rf csrc simv simv.daidir ucli.key vc_hdrs.h
	rm -rf DVEfiles inter.vpd .inter.vpd.uvm

## Clean results directory
clean-results:
	@echo "[AIa-VO] Cleaning results..."
	rm -rf $(RESULTS_DIR)

## Clean everything
clean-all: clean clean-results
	@echo "[AIa-VO] Full clean complete."

## Create zip archive
zip:
	@echo "[AIa-VO] Creating project archive..."
	@mkdir -p $(PROJECT_ROOT)/dist
	cd $(PROJECT_ROOT)/.. && zip -r \
		$(PROJECT_ROOT)/dist/AIaVO_ALU_Verification_$(shell date +%Y%m%d).zip \
		$(notdir $(PROJECT_ROOT)) \
		-x "$(notdir $(PROJECT_ROOT))/.git/*" \
		-x "$(notdir $(PROJECT_ROOT))/sim_work/*" \
		-x "$(notdir $(PROJECT_ROOT))/results/*" \
		-x "$(notdir $(PROJECT_ROOT))/dist/*" \
		-x "$(notdir $(PROJECT_ROOT))/__pycache__/*" \
		-x "$(notdir $(PROJECT_ROOT))/*/__pycache__/*" \
		-x "$(notdir $(PROJECT_ROOT))/*/*/__pycache__/*"
	@echo "[AIa-VO] Archive created: dist/AIaVO_ALU_Verification_$(shell date +%Y%m%d).zip"
