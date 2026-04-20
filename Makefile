# =============================================================================
# ALU Testbench UVM 8-Bit with RL Verification Optimization
# =============================================================================
# Makefile for Synopsys VCS simulation with optional RL-guided stimulus
#
# Usage:
#   make help                    - Show all available targets
#   make sim                     - Run baseline random simulation
#   make sim_rl                  - Run RL-guided simulation (file mode)
#   make sim_rl_live             - Run RL-guided simulation (live pipe mode)
#   make compare                 - Run RL vs Random comparison (Python only)
#   make train                   - Train RL agent only
#   make all                     - Full flow: train + generate + simulate both
#   make clean                   - Clean build artifacts
#
# Configuration Variables:
#   USE_RL       = 0|1           - Enable RL stimulus (default: 0)
#   RL_ALGO      = PPO|DQN|A2C  - RL algorithm (default: PPO)
#   NUM_TX       = <N>           - Number of transactions (default: 1000)
#   TRAIN_STEPS  = <N>           - RL training timesteps (default: 50000)
#   SEED         = <N>           - Random seed (default: 42)
#   VERBOSITY    = UVM_LOW|UVM_MEDIUM|UVM_HIGH|UVM_FULL
#   GUI          = 0|1           - Launch DVE GUI (default: 0)
#   COV          = 0|1           - Enable coverage collection (default: 1)
#   WAVES        = 0|1           - Dump waveforms (default: 0)
# =============================================================================

# ---- Tool Configuration ----
VCS          ?= vcs
PYTHON       ?= python3
PIP          ?= pip3

# ---- Simulation Configuration ----
USE_RL       ?= 0
RL_ALGO      ?= PPO
RL_MODE      ?= file
NUM_TX       ?= 1000
TRAIN_STEPS  ?= 50000
SEED         ?= 42
VERBOSITY    ?= UVM_LOW
GUI          ?= 0
COV          ?= 1
WAVES        ?= 0

# ---- Directory Structure ----
DUT_DIR      = DUT
TB_DIR       = Testbench
BRIDGE_DIR   = $(TB_DIR)/bridge
SEQ_DIR      = $(TB_DIR)/sequences
TEST_DIR     = $(TB_DIR)/tests
RL_DIR       = rl
WORK_DIR     = sim_work
LOG_DIR      = logs
MODEL_DIR    = models
RESULT_DIR   = results
SCRIPT_DIR   = scripts

# ---- Source Files ----
DUT_FILES    = $(DUT_DIR)/ALU_DUT.sv

INTF_FILE    = $(DUT_DIR)/ALU_interface.sv

# Standard (non-RL) sources
TB_PKG_STD   = $(TB_DIR)/ALU_pkg.sv
TB_TOP_STD   = $(TB_DIR)/ALU_Top.sv

# RL-enhanced sources
TB_PKG_RL    = $(TB_DIR)/ALU_RL_pkg.sv
TB_TOP_RL    = $(TB_DIR)/ALU_RL_Top.sv

# ---- VCS Compile Options ----
VCS_OPTS     = -full64 -sverilog -timescale=1ns/1ps
VCS_OPTS    += -ntb_opts uvm-1.2
VCS_OPTS    += +incdir+$(DUT_DIR)
VCS_OPTS    += +incdir+$(TB_DIR)
VCS_OPTS    += +incdir+$(BRIDGE_DIR)
VCS_OPTS    += +incdir+$(SEQ_DIR)
VCS_OPTS    += +incdir+$(TEST_DIR)

# UVM home (auto-detect from VCS)
ifdef UVM_HOME
VCS_OPTS    += +incdir+$(UVM_HOME)/src
endif

# Debug options
VCS_OPTS    += -debug_access+all
VCS_OPTS    += +define+UVM_NO_DEPRECATED

# Coverage options
ifeq ($(COV),1)
VCS_OPTS    += -cm line+cond+fsm+tgl+branch+assert
VCS_OPTS    += -cm_dir $(WORK_DIR)/coverage.vdb
endif

# Waveform dump
ifeq ($(WAVES),1)
VCS_OPTS    += +define+DUMP_WAVES
VCS_OPTS    += -kdb
endif

# ---- VCS Runtime Options ----
SIM_OPTS     = +UVM_VERBOSITY=$(VERBOSITY)
SIM_OPTS    += +UVM_NO_RELNOTES

ifeq ($(COV),1)
SIM_OPTS    += -cm line+cond+fsm+tgl+branch+assert
SIM_OPTS    += -cm_dir $(WORK_DIR)/coverage.vdb
endif

ifeq ($(GUI),1)
SIM_OPTS    += -gui
endif

ifeq ($(WAVES),1)
SIM_OPTS    += +DUMP_WAVES
endif

# ---- Output Binary ----
SIM_BIN_STD  = $(WORK_DIR)/simv_std
SIM_BIN_RL   = $(WORK_DIR)/simv_rl

# ---- Stimulus/Response Files ----
STIM_FILE    = $(WORK_DIR)/rl_stimuli.txt
RESP_FILE    = $(WORK_DIR)/sv_responses.txt
COV_FILE_RL  = $(WORK_DIR)/rl_coverage_report.txt
COV_FILE_STD = $(WORK_DIR)/baseline_coverage_report.txt

# =============================================================================
# TARGETS
# =============================================================================

.PHONY: help all clean setup compile_std compile_rl sim sim_rl sim_rl_live \
        train generate compare install_deps check_deps dirs

# ---- Help ----
help:
	@echo "================================================================="
	@echo " ALU UVM Testbench with RL Verification Optimization"
	@echo "================================================================="
	@echo ""
	@echo "SIMULATION TARGETS:"
	@echo "  make sim               - Run baseline random simulation"
	@echo "  make sim_rl            - Run RL-guided simulation (file mode)"
	@echo "  make sim_rl_live       - Run RL-guided simulation (live mode)"
	@echo "  make sim TEST=<name>   - Run specific test"
	@echo ""
	@echo "RL TARGETS:"
	@echo "  make train             - Train RL agent"
	@echo "  make generate          - Generate RL stimuli from trained model"
	@echo "  make compare           - Run RL vs Random comparison (Python)"
	@echo ""
	@echo "BUILD TARGETS:"
	@echo "  make compile_std       - Compile standard testbench"
	@echo "  make compile_rl        - Compile RL-enhanced testbench"
	@echo "  make all               - Full flow: train + sim_rl + sim + compare"
	@echo ""
	@echo "UTILITY TARGETS:"
	@echo "  make clean             - Clean all artifacts"
	@echo "  make install_deps      - Install Python dependencies"
	@echo "  make check_deps        - Check tool availability"
	@echo "  make coverage_report   - Generate coverage report"
	@echo "  make zip               - Create repo archive"
	@echo ""
	@echo "CONFIGURATION:"
	@echo "  USE_RL=0|1             - Enable RL (default: 0)"
	@echo "  RL_ALGO=PPO|DQN|A2C   - RL algorithm (default: PPO)"
	@echo "  NUM_TX=<N>             - Transactions (default: 1000)"
	@echo "  TRAIN_STEPS=<N>        - Training steps (default: 50000)"
	@echo "  SEED=<N>               - Random seed (default: 42)"
	@echo "  VERBOSITY=UVM_*        - UVM verbosity (default: UVM_LOW)"
	@echo "  GUI=0|1                - DVE GUI (default: 0)"
	@echo "  COV=0|1                - Coverage (default: 1)"
	@echo "  WAVES=0|1              - Waveforms (default: 0)"
	@echo ""
	@echo "EXAMPLES:"
	@echo "  make sim NUM_TX=5000 COV=1"
	@echo "  make sim_rl RL_ALGO=PPO NUM_TX=1000 TRAIN_STEPS=100000"
	@echo "  make compare RL_ALGO=DQN TRAIN_STEPS=50000"
	@echo "  make all RL_ALGO=A2C"
	@echo "================================================================="

# ---- Directory Setup ----
dirs:
	@mkdir -p $(WORK_DIR) $(LOG_DIR) $(MODEL_DIR) $(RESULT_DIR)

# ---- Dependency Check ----
check_deps:
	@echo "Checking dependencies..."
	@which $(VCS) > /dev/null 2>&1 && echo "[OK] VCS found" || echo "[!!] VCS not found"
	@which $(PYTHON) > /dev/null 2>&1 && echo "[OK] Python found" || echo "[!!] Python not found"
	@$(PYTHON) -c "import gymnasium" 2>/dev/null && echo "[OK] gymnasium" || echo "[!!] gymnasium not installed"
	@$(PYTHON) -c "import stable_baselines3" 2>/dev/null && echo "[OK] stable-baselines3" || echo "[!!] stable-baselines3 not installed"
	@$(PYTHON) -c "import numpy" 2>/dev/null && echo "[OK] numpy" || echo "[!!] numpy not installed"
	@$(PYTHON) -c "import torch" 2>/dev/null && echo "[OK] torch" || echo "[!!] torch not installed"

# ---- Install Python Dependencies ----
install_deps:
	$(PIP) install -r requirements.txt

# ---- Compile Standard Testbench ----
compile_std: dirs
	@echo "========================================"
	@echo " Compiling Standard ALU Testbench"
	@echo "========================================"
	$(VCS) $(VCS_OPTS) \
		$(DUT_FILES) \
		$(TB_PKG_STD) \
		$(TB_TOP_STD) \
		-o $(SIM_BIN_STD) \
		-l $(LOG_DIR)/compile_std.log

# ---- Compile RL-Enhanced Testbench ----
compile_rl: dirs
	@echo "========================================"
	@echo " Compiling RL-Enhanced ALU Testbench"
	@echo "========================================"
	$(VCS) $(VCS_OPTS) \
		$(DUT_FILES) \
		$(TB_PKG_RL) \
		$(TB_TOP_RL) \
		-o $(SIM_BIN_RL) \
		-l $(LOG_DIR)/compile_rl.log

# ---- Run Baseline Random Simulation ----
sim: compile_std
	@echo "========================================"
	@echo " Running Baseline Random Simulation"
	@echo " Transactions: $(NUM_TX)"
	@echo "========================================"
	cd $(WORK_DIR) && ../$(SIM_BIN_STD) \
		$(SIM_OPTS) \
		+UVM_TESTNAME=ALU_Test \
		+NUM_TX=$(NUM_TX) \
		+COV_FILE=$(COV_FILE_STD) \
		-l ../$(LOG_DIR)/sim_baseline.log

# ---- Run RL-Guided Simulation (File Mode) ----
sim_rl: compile_rl generate
	@echo "========================================"
	@echo " Running RL-Guided Simulation"
	@echo " Algorithm: $(RL_ALGO)"
	@echo " Transactions: $(NUM_TX)"
	@echo " Stimulus file: $(STIM_FILE)"
	@echo "========================================"
	cd $(WORK_DIR) && ../$(SIM_BIN_RL) \
		$(SIM_OPTS) \
		+UVM_TESTNAME=ALU_RL_Test \
		+RL_MODE=file \
		+RL_STIM_FILE=../$(STIM_FILE) \
		+RL_RESP_FILE=../$(RESP_FILE) \
		+RL_COV_FILE=../$(COV_FILE_RL) \
		+RL_MAX_TX=$(NUM_TX) \
		-l ../$(LOG_DIR)/sim_rl.log

# ---- Run RL-Guided Simulation (Live Pipe Mode) ----
sim_rl_live: compile_rl
	@echo "========================================"
	@echo " Running RL Live Simulation"
	@echo " Start Python RL agent in another terminal:"
	@echo " $(PYTHON) -m rl.run_rl_verification --mode live"
	@echo "========================================"
	cd $(WORK_DIR) && ../$(SIM_BIN_RL) \
		$(SIM_OPTS) \
		+UVM_TESTNAME=ALU_RL_Test \
		+RL_MODE=live \
		+RL_PIPE_DIR=/tmp/alu_rl_bridge \
		+RL_MAX_TX=$(NUM_TX) \
		-l ../$(LOG_DIR)/sim_rl_live.log

# ---- Run Baseline Simulation with Configurable TX Count ----
sim_baseline: compile_rl
	@echo "========================================"
	@echo " Running Baseline Test"
	@echo " Transactions: $(NUM_TX)"
	@echo "========================================"
	cd $(WORK_DIR) && ../$(SIM_BIN_RL) \
		$(SIM_OPTS) \
		+UVM_TESTNAME=ALU_Baseline_Test \
		+NUM_TX=$(NUM_TX) \
		+COV_FILE=../$(COV_FILE_STD) \
		-l ../$(LOG_DIR)/sim_baseline.log

# ---- Train RL Agent ----
train: dirs
	@echo "========================================"
	@echo " Training RL Agent"
	@echo " Algorithm: $(RL_ALGO)"
	@echo " Timesteps: $(TRAIN_STEPS)"
	@echo " Seed: $(SEED)"
	@echo "========================================"
	$(PYTHON) -m rl.train \
		--algorithm $(RL_ALGO) \
		--timesteps $(TRAIN_STEPS) \
		--max-transactions $(NUM_TX) \
		--seed $(SEED) \
		--model-dir $(MODEL_DIR) \
		--log-dir $(LOG_DIR)

# ---- Generate RL Stimuli ----
generate: dirs train
	@echo "========================================"
	@echo " Generating RL Stimuli"
	@echo " Algorithm: $(RL_ALGO)"
	@echo " Transactions: $(NUM_TX)"
	@echo "========================================"
	$(PYTHON) -m rl.run_rl_verification \
		--mode train-and-generate \
		--algorithm $(RL_ALGO) \
		--timesteps $(TRAIN_STEPS) \
		--num-stimuli $(NUM_TX) \
		--seed $(SEED) \
		--work-dir $(WORK_DIR)

# ---- Generate Random Stimuli (for comparison) ----
generate_random: dirs
	@echo "Generating random stimuli..."
	$(PYTHON) -m rl.run_rl_verification \
		--mode random \
		--num-stimuli $(NUM_TX) \
		--seed $(SEED) \
		--work-dir $(WORK_DIR)

# ---- Run RL vs Random Comparison (Python offline) ----
compare: dirs
	@echo "========================================"
	@echo " RL vs Random Comparison"
	@echo " Algorithm: $(RL_ALGO)"
	@echo " Timesteps: $(TRAIN_STEPS)"
	@echo " Episodes: 10"
	@echo "========================================"
	$(PYTHON) -m rl.compare \
		--algorithm $(RL_ALGO) \
		--timesteps $(TRAIN_STEPS) \
		--max-transactions $(NUM_TX) \
		--episodes 10 \
		--seed $(SEED) \
		--output-dir $(RESULT_DIR)

# ---- Full Flow ----
all: dirs install_deps train sim_rl sim compare
	@echo "========================================"
	@echo " Full flow complete!"
	@echo " Results in: $(RESULT_DIR)/"
	@echo "========================================"

# ---- Coverage Report (VCS) ----
coverage_report:
	@echo "Generating coverage report..."
	@if [ -d "$(WORK_DIR)/coverage.vdb" ]; then \
		urg -dir $(WORK_DIR)/coverage.vdb -report $(RESULT_DIR)/coverage_html; \
		echo "Coverage report: $(RESULT_DIR)/coverage_html/dashboard.html"; \
	else \
		echo "No coverage database found. Run simulation with COV=1 first."; \
	fi

# ---- Create ZIP Archive ----
zip: clean
	@echo "Creating repository archive..."
	@cd .. && zip -r ALU_Testbench_UVM_8Bit_RL.zip ALU_Testbench_UVM_8Bit/ \
		-x "ALU_Testbench_UVM_8Bit/.git/*" \
		-x "ALU_Testbench_UVM_8Bit/sim_work/*" \
		-x "ALU_Testbench_UVM_8Bit/logs/*" \
		-x "ALU_Testbench_UVM_8Bit/models/*" \
		-x "ALU_Testbench_UVM_8Bit/__pycache__/*" \
		-x "ALU_Testbench_UVM_8Bit/rl/__pycache__/*"
	@echo "Archive: ../ALU_Testbench_UVM_8Bit_RL.zip"

# ---- Clean ----
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(WORK_DIR) $(LOG_DIR) $(MODEL_DIR) $(RESULT_DIR)
	rm -rf csrc *.daidir *.vpd *.fsdb *.log *.key
	rm -rf simv simv.daidir ucli.key vc_hdrs.h
	rm -rf DVEfiles urgReport .inter.vpd.uvm
	rm -rf __pycache__ rl/__pycache__
	rm -rf /tmp/alu_rl_bridge
	@echo "Clean complete."

# ---- Clean only simulation artifacts (keep models/logs) ----
clean_sim:
	rm -rf $(WORK_DIR)/simv* $(WORK_DIR)/csrc
	rm -rf csrc *.daidir simv simv.daidir

.DEFAULT_GOAL := help
