# ============================================================================
#  AId-VO — AI-Directed Verification Optimization
#  Makefile for 8-bit ALU UVM Testbench with RL-based Coverage Acceleration
# ============================================================================
#
#  IMPORTANT: The original UVM testbench (DUT/ and Testbench/) is NEVER
#  modified.  All AI logic lives in Python (ai/) and interacts with the
#  simulation purely through seeds, plusargs, and log/coverage parsing.
#
# ── Quick start ─────────────────────────────────────────────────────────────
#  make help               Show this help
#  make py-smoke           Smoke-test the Python RL stack (no VCS required)
#  make train              Train the default RL agent (PPO)
#  make compare            Compare PPO + DQN + A2C vs random baseline
#  make sim                Run a single VCS simulation (requires VCS)
#  make sim-ai             Run AI-directed VCS verification loop
#  make report             Generate comparison report
#  make zip                Package the entire repo for download
# ============================================================================

# ── Configuration (override on command line) ────────────────────────────────
AI_ENABLED        ?= 1
AI_ALGORITHM      ?= ppo
AI_TIMESTEPS      ?= 50000
AI_MAX_ITER       ?= 50
AI_TXN_PER_ITER   ?= 1000
TARGET_COVERAGE   ?= 95.0
SEED              ?= 42
SIM_MODE          ?= python
VERBOSITY         ?= UVM_LOW
NUM_ITEMS         ?= 5000
TEST              ?= ALU_Test
OUTPUT_DIR        ?= results
LEARNING_RATE     ?= 3e-4
NUM_EVAL_EPISODES ?= 10

# ── Paths ───────────────────────────────────────────────────────────────────
PROJ_ROOT   := $(shell pwd)
DUT_DIR     := $(PROJ_ROOT)/DUT
TB_DIR      := $(PROJ_ROOT)/Testbench
WORK_DIR    := $(PROJ_ROOT)/work
COV_DIR     := $(PROJ_ROOT)/coverage
LOG_DIR     := $(PROJ_ROOT)/logs
SCRIPTS_DIR := $(PROJ_ROOT)/scripts
PYTHON      := python3

# ── VCS settings ────────────────────────────────────────────────────────────
VCS_FLAGS   := -full64 -sverilog +acc -timescale=1ns/1ps -ntb_opts uvm-1.2
VCS_INCS    := +incdir+$(TB_DIR) +incdir+$(DUT_DIR)
VCS_SRCS    := $(DUT_DIR)/ALU_DUT.sv $(DUT_DIR)/ALU_interface.sv \
               $(TB_DIR)/ALU_pkg.sv $(TB_DIR)/ALU_Top.sv
VCS_COV     := -cm line+cond+fsm+branch+tgl
SIMV        := $(WORK_DIR)/simv

# ============================================================================
#  TARGETS
# ============================================================================

.PHONY: help install py-smoke train train-ppo train-dqn train-a2c \
        evaluate compare report \
        sim sim-compile sim-run sim-coverage sim-ai sim-baseline \
        clean clean-results clean-all zip test

# ── Help ────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  AId-VO — AI-Directed Verification Optimization"
	@echo "  ================================================"
	@echo ""
	@echo "  PYTHON / RL TARGETS (no VCS required):"
	@echo "    make install             Install Python dependencies"
	@echo "    make py-smoke            Quick smoke test of RL stack"
	@echo "    make test                Run Python unit tests"
	@echo "    make train               Train RL agent          (AI_ALGORITHM=$(AI_ALGORITHM))"
	@echo "    make train-ppo           Train PPO agent"
	@echo "    make train-dqn           Train DQN agent"
	@echo "    make train-a2c           Train A2C agent"
	@echo "    make evaluate            Evaluate trained agent vs baseline"
	@echo "    make compare             Full comparison: PPO+DQN+A2C vs baseline"
	@echo "    make report              Generate comparison report"
	@echo ""
	@echo "  VCS SIMULATION TARGETS (require Synopsys VCS):"
	@echo "    make sim                 Single VCS simulation run"
	@echo "    make sim-compile         Compile only (VCS)"
	@echo "    make sim-run             Run simulation only"
	@echo "    make sim-coverage        Run with coverage collection"
	@echo "    make sim-ai              AI-directed VCS verification"
	@echo "    make sim-baseline        Baseline VCS verification"
	@echo ""
	@echo "  UTILITY:"
	@echo "    make clean               Remove build artifacts"
	@echo "    make clean-results       Remove results directory"
	@echo "    make clean-all           Remove everything (build + results)"
	@echo "    make zip                 Create distributable archive"
	@echo ""
	@echo "  CONFIGURATION VARIABLES (override with make VAR=val):"
	@echo "    AI_ENABLED        = $(AI_ENABLED)          (0=off, 1=on)"
	@echo "    AI_ALGORITHM      = $(AI_ALGORITHM)       (ppo, dqn, a2c)"
	@echo "    AI_TIMESTEPS      = $(AI_TIMESTEPS)      (training steps)"
	@echo "    AI_MAX_ITER       = $(AI_MAX_ITER)          (verification iterations)"
	@echo "    AI_TXN_PER_ITER   = $(AI_TXN_PER_ITER)       (transactions per iteration)"
	@echo "    TARGET_COVERAGE   = $(TARGET_COVERAGE)       (target coverage %)"
	@echo "    SEED              = $(SEED)          (random seed)"
	@echo "    SIM_MODE          = $(SIM_MODE)     (python or vcs)"
	@echo "    NUM_ITEMS         = $(NUM_ITEMS)       (VCS transactions)"
	@echo "    TEST              = $(TEST)    (UVM test name)"
	@echo "    VERBOSITY         = $(VERBOSITY)    (UVM verbosity)"
	@echo "    LEARNING_RATE     = $(LEARNING_RATE)       (RL learning rate)"
	@echo "    NUM_EVAL_EPISODES = $(NUM_EVAL_EPISODES)         (evaluation episodes)"
	@echo "    OUTPUT_DIR        = $(OUTPUT_DIR)    (output directory)"
	@echo ""

# ── Python setup ────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

# ── Smoke test (no VCS) ────────────────────────────────────────────────────
py-smoke:
	@echo "[AId-VO] Running Python smoke test ..."
	$(PYTHON) -c "\
from ai.environments.alu_sim_model import ALUModel, CoverageModel, PythonSimRunner, StimulusGenerator; \
sim = PythonSimRunner(); \
gen = StimulusGenerator(seed=42); \
txns = gen.generate_default(500); \
cov = sim.run_batch(txns); \
print(f'Smoke test PASSED — Coverage: {cov:.1f}% ({sim.coverage.total_covered}/{CoverageModel.NUM_BINS} bins) after 500 txns'); \
assert cov > 0, 'Coverage should be > 0'"

# ── Unit tests ──────────────────────────────────────────────────────────────
test:
	$(PYTHON) tests/test_rl_stack.py

# ── Training ────────────────────────────────────────────────────────────────
train:
	$(PYTHON) -m ai.train \
		--algorithm $(AI_ALGORITHM) \
		--timesteps $(AI_TIMESTEPS) \
		--seed $(SEED) \
		--target-coverage $(TARGET_COVERAGE) \
		--max-steps $(AI_MAX_ITER) \
		--learning-rate $(LEARNING_RATE) \
		--output-dir $(OUTPUT_DIR)

train-ppo:
	$(MAKE) train AI_ALGORITHM=ppo

train-dqn:
	$(MAKE) train AI_ALGORITHM=dqn

train-a2c:
	$(MAKE) train AI_ALGORITHM=a2c

# ── Evaluation ──────────────────────────────────────────────────────────────
evaluate:
	$(PYTHON) -m ai.evaluate \
		--algorithm $(AI_ALGORITHM) \
		--model $(OUTPUT_DIR)/models/$(AI_ALGORITHM)_model \
		--episodes $(NUM_EVAL_EPISODES) \
		--seed $(SEED) \
		--target-coverage $(TARGET_COVERAGE) \
		--max-steps $(AI_MAX_ITER) \
		--output-dir $(OUTPUT_DIR)

# ── Comparison ──────────────────────────────────────────────────────────────
compare:
	$(PYTHON) -m ai.run_comparison \
		--algorithms ppo dqn a2c \
		--timesteps $(AI_TIMESTEPS) \
		--seed $(SEED) \
		--target-coverage $(TARGET_COVERAGE) \
		--max-iterations $(AI_MAX_ITER) \
		--transactions-per-iter $(AI_TXN_PER_ITER) \
		--output-dir $(OUTPUT_DIR)

report:
	@echo "[AId-VO] Generating report from $(OUTPUT_DIR)/comparison.json ..."
	$(PYTHON) -c "\
from ai.analysis.reporter import ReportGenerator; \
import json; \
data = json.load(open('$(OUTPUT_DIR)/comparison.json')); \
rg = ReportGenerator('$(OUTPUT_DIR)'); \
rg.generate_full_report(data); \
print('Report generated: $(OUTPUT_DIR)/report.md')"

# ── VCS simulation ─────────────────────────────────────────────────────────
sim-compile: | $(WORK_DIR)
	vcs $(VCS_FLAGS) $(VCS_INCS) $(VCS_SRCS) -o $(SIMV) -Mdir=$(WORK_DIR)/csrc

sim-run: $(SIMV)
	@mkdir -p $(LOG_DIR)
	$(SIMV) +UVM_TESTNAME=$(TEST) +UVM_VERBOSITY=$(VERBOSITY) \
		+ntb_random_seed=$(SEED) \
		2>&1 | tee $(LOG_DIR)/sim_seed$(SEED).log

sim-coverage: | $(WORK_DIR) $(COV_DIR)
	vcs $(VCS_FLAGS) $(VCS_INCS) $(VCS_SRCS) $(VCS_COV) \
		-o $(SIMV) -Mdir=$(WORK_DIR)/csrc -cm_dir $(COV_DIR)/compile_db
	$(SIMV) +UVM_TESTNAME=$(TEST) +UVM_VERBOSITY=$(VERBOSITY) \
		+ntb_random_seed=$(SEED) \
		$(VCS_COV) -cm_dir $(COV_DIR)/sim_db -cm_log $(COV_DIR)/cm.log \
		2>&1 | tee $(LOG_DIR)/sim_cov_seed$(SEED).log
	urg -dir $(COV_DIR)/sim_db -report $(COV_DIR)/urgReport 2>/dev/null || true

sim: sim-compile sim-run

sim-ai:
	$(SCRIPTS_DIR)/run_ai_verification.sh \
		--algorithm $(AI_ALGORITHM) \
		--timesteps $(AI_TIMESTEPS) \
		--iterations $(AI_MAX_ITER) \
		--target $(TARGET_COVERAGE) \
		--txn-per-iter $(AI_TXN_PER_ITER) \
		--seed $(SEED) \
		--mode $(SIM_MODE) \
		--output-dir $(OUTPUT_DIR)

sim-baseline:
	$(SCRIPTS_DIR)/run_vcs.sh \
		--seed $(SEED) \
		--test $(TEST) \
		--verbosity $(VERBOSITY) \
		--coverage \
		--log $(LOG_DIR)/baseline.log

# ── Directories ─────────────────────────────────────────────────────────────
$(WORK_DIR) $(COV_DIR) $(LOG_DIR):
	mkdir -p $@

# ── Cleanup ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(WORK_DIR) $(COV_DIR) $(LOG_DIR)
	rm -rf simv simv.daidir csrc ucli.key
	rm -rf DVEfiles inter.vpd vc_hdrs.h
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

clean-results:
	rm -rf $(OUTPUT_DIR)

clean-all: clean clean-results
	rm -rf models

# ── Package ─────────────────────────────────────────────────────────────────
zip:
	@echo "[AId-VO] Creating distributable archive ..."
	cd $(PROJ_ROOT)/.. && \
	zip -r ALU_Testbench_UVM_8Bit_AIdVO.zip \
		$(notdir $(PROJ_ROOT))/ \
		-x "$(notdir $(PROJ_ROOT))/.git/*" \
		-x "$(notdir $(PROJ_ROOT))/work/*" \
		-x "$(notdir $(PROJ_ROOT))/coverage/*" \
		-x "$(notdir $(PROJ_ROOT))/logs/*" \
		-x "$(notdir $(PROJ_ROOT))/results/*" \
		-x "$(notdir $(PROJ_ROOT))/models/*" \
		-x "$(notdir $(PROJ_ROOT))/__pycache__/*" \
		-x "*/__pycache__/*" \
		-x "*.pyc"
	@echo "[AId-VO] Archive: ../ALU_Testbench_UVM_8Bit_AIdVO.zip"
