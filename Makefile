# ============================================================================
# Top-level Makefile - 8-bit ALU UVM + Python RL
# ============================================================================
# Primary simulator : Synopsys VCS (UVM 1.2)
# Optional AI/ML    : Gymnasium + stable-baselines3 (PPO / DQN / A2C)
# Bridge            : PyHDL-IF (no DPI-C bridge code)
#
# Quick start
# -----------
#   make sim TEST=alu_random_test NUM_ITEMS=5000
#   make rl-sim ALGO=PPO NUM_ITEMS=5000 MODEL=models/ppo/ppo_final.zip
#   make py-train ALGO=PPO STEPS=50000
#   make py-compare
#   make legacy            # run the original Testbench/ flow, unchanged
#
# Key variables (all can be set on the command line)
# --------------------------------------------------
#   TEST         = alu_random_test | alu_directed_test | alu_rl_test
#   USE_RL       = 0 | 1           (auto-set by targets below)
#   ALGO         = PPO | DQN | A2C (Python RL algorithm)
#   NUM_ITEMS    = number of stimuli per simulation
#   SEED         = random seed for the simulator
#   UVM_VERBOSITY= UVM_LOW | UVM_MEDIUM | UVM_HIGH | UVM_DEBUG
#   COV          = 0 | 1           (enable UVM functional coverage)
#   DUMP         = 0 | 1           (dump VCD waves)
#   GUI          = 0 | 1           (invoke Verdi/dve)
#   TIMEOUT_NS   = simulator watchdog in ns
#   MODEL        = path to trained SB3 model (for rl-sim target)
#   STEPS        = training steps for py-train
#   MAX_STEPS    = per-episode steps in gym env
# ============================================================================

SHELL := /bin/bash

# ------ User-settable parameters ------
TEST          ?= alu_random_test
USE_RL        ?= 0
ALGO          ?= PPO
NUM_ITEMS     ?= 5000
SEED          ?= 1
UVM_VERBOSITY ?= UVM_MEDIUM
COV           ?= 0
DUMP          ?= 0
GUI           ?= 0
TIMEOUT_NS    ?= 10000000
MODEL         ?=
STEPS         ?= 50000
MAX_STEPS     ?= 1000
EPISODES      ?= 5

# ------ Paths ------
ROOT_DIR   := $(shell pwd)
TB_DIR     := $(ROOT_DIR)/tb_rl
BUILD_DIR  := $(ROOT_DIR)/sim/vcs
LOG_DIR    := $(BUILD_DIR)/logs
RESULTS    := $(ROOT_DIR)/docs/results

PYTHON     ?= python3
PIP        ?= pip3

# PyHDL-IF package-provided SV sources and shared libs
PYHDLIF_SHARE := $(shell $(PYTHON) -m hdl_if share 2>/dev/null)
PYHDLIF_LIB   := $(shell $(PYTHON) -m hdl_if libs 2>/dev/null)

# ------ VCS flags ------
VCS       ?= vcs
SIMV      := $(BUILD_DIR)/simv

VCS_COMMON_FLAGS := \
	-full64 \
	-sverilog -ntb_opts uvm-1.2 \
	-timescale=1ns/1ps \
	-debug_access+all \
	-l $(LOG_DIR)/compile.log \
	+define+UVM_NO_DPI

ifeq ($(COV),1)
VCS_COMMON_FLAGS += -cm line+cond+fsm+tgl+branch+assert
RUN_COV_FLAGS    := -cm line+cond+fsm+tgl+branch+assert -cm_name $(TEST)
else
RUN_COV_FLAGS    :=
endif

ifeq ($(DUMP),1)
RUN_PLUS_DUMP := +DUMP
else
RUN_PLUS_DUMP :=
endif

# ------ Compile file lists ------
PYHDLIF_FILELIST :=
ifneq ($(strip $(PYHDLIF_SHARE)),)
PYHDLIF_FILELIST := \
	+incdir+$(PYHDLIF_SHARE)/dpi \
	$(PYHDLIF_SHARE)/dpi/pyhdl_if.sv \
	$(PYHDLIF_SHARE)/pyhdl_if_req_fifo.sv \
	$(PYHDLIF_SHARE)/pyhdl_if_rsp_fifo.sv \
	$(PYHDLIF_SHARE)/pyhdl_if_reqrsp_fifo.sv
endif

# ------ Targets ------
.PHONY: help sim rl-sim random-sim directed-sim legacy compile elab run \
        py-train py-eval py-random py-compare py-smoke deps \
        clean distclean show-config

help:
	@echo "Targets:"
	@echo "  make sim TEST=<test>          run a UVM test ($$(TEST) default=$(TEST))"
	@echo "  make rl-sim                   alias for sim TEST=alu_rl_test USE_RL=1"
	@echo "  make random-sim               alias for sim TEST=alu_random_test"
	@echo "  make directed-sim             alias for sim TEST=alu_directed_test"
	@echo "  make legacy                   run the original unchanged Testbench/ flow"
	@echo "  make py-train ALGO=PPO        train a SB3 policy on the offline gym env"
	@echo "  make py-eval                  evaluate a trained policy"
	@echo "  make py-random                pure-random baseline for comparison"
	@echo "  make py-compare               render RL vs Random comparison report"
	@echo "  make py-smoke                 quick sanity check (train+eval+compare)"
	@echo "  make deps                     pip-install all Python dependencies"
	@echo "  make show-config              dump current configuration"
	@echo "  make clean / distclean        remove build artefacts"

show-config:
	@echo "TEST           = $(TEST)"
	@echo "USE_RL         = $(USE_RL)"
	@echo "ALGO           = $(ALGO)"
	@echo "NUM_ITEMS      = $(NUM_ITEMS)"
	@echo "SEED           = $(SEED)"
	@echo "UVM_VERBOSITY  = $(UVM_VERBOSITY)"
	@echo "COV            = $(COV)"
	@echo "DUMP           = $(DUMP)"
	@echo "GUI            = $(GUI)"
	@echo "MODEL          = $(MODEL)"
	@echo "PYHDLIF_SHARE  = $(PYHDLIF_SHARE)"
	@echo "PYHDLIF_LIB    = $(PYHDLIF_LIB)"

# ---- HDL simulation ----
$(LOG_DIR):
	@mkdir -p $(LOG_DIR)

compile: | $(LOG_DIR)
	cd $(BUILD_DIR) && $(VCS) $(VCS_COMMON_FLAGS) \
		$(PYHDLIF_FILELIST) \
		-f $(TB_DIR)/filelist.f \
		-load $(PYHDLIF_LIB) \
		-top testbench_top \
		-o $(SIMV)

run: | $(LOG_DIR)
	cd $(BUILD_DIR) && $(SIMV) \
		+UVM_TESTNAME=$(TEST) \
		+UVM_VERBOSITY=$(UVM_VERBOSITY) \
		+USE_RL=$(USE_RL) \
		+ALGO=$(ALGO) \
		+NUM_ITEMS=$(NUM_ITEMS) \
		+SEED=$(SEED) \
		+TIMEOUT_NS=$(TIMEOUT_NS) \
		$(RUN_PLUS_DUMP) \
		$(RUN_COV_FLAGS) \
		+ntb_random_seed=$(SEED) \
		-l $(LOG_DIR)/$(TEST).log

sim: compile run
	@echo "[sim] $(TEST) finished - log: $(LOG_DIR)/$(TEST).log"

random-sim:
	$(MAKE) sim TEST=alu_random_test USE_RL=0

directed-sim:
	$(MAKE) sim TEST=alu_directed_test USE_RL=0

rl-sim:
	@if [ -z "$(MODEL)" ]; then \
	  echo "ERROR: set MODEL=path/to/trained.zip for rl-sim"; exit 1; \
	fi
	$(MAKE) sim TEST=alu_rl_test USE_RL=1

# ---- Legacy flow (untouched files under Testbench/) ----
legacy: | $(LOG_DIR)
	cd $(BUILD_DIR) && $(VCS) $(VCS_COMMON_FLAGS) \
		+incdir+$(ROOT_DIR)/Testbench +incdir+$(ROOT_DIR)/DUT \
		$(ROOT_DIR)/DUT/ALU_interface.sv \
		$(ROOT_DIR)/DUT/ALU_DUT.sv \
		$(ROOT_DIR)/Testbench/ALU_pkg.sv \
		$(ROOT_DIR)/Testbench/ALU_Top.sv \
		-top Top -o $(BUILD_DIR)/legacy_simv \
		-l $(LOG_DIR)/legacy_compile.log
	cd $(BUILD_DIR) && ./legacy_simv \
		+UVM_TESTNAME=ALU_Test +UVM_VERBOSITY=$(UVM_VERBOSITY) \
		+ntb_random_seed=$(SEED) \
		-l $(LOG_DIR)/legacy_run.log

# ---- Python RL flow ----
deps:
	$(PIP) install -r requirements.txt

py-train:
	$(PYTHON) -m rl.train --algo $(ALGO) --steps $(STEPS) \
		--max-steps $(MAX_STEPS) --seed $(SEED) \
		--out models/$(shell echo $(ALGO) | tr A-Z a-z)

py-eval:
	@if [ -z "$(MODEL)" ]; then \
	  MODEL=models/$(shell echo $(ALGO) | tr A-Z a-z)/$(shell echo $(ALGO) | tr A-Z a-z)_final.zip; \
	fi; \
	$(PYTHON) -m rl.evaluate --model $${MODEL:-models/$(shell echo $(ALGO) | tr A-Z a-z)/$(shell echo $(ALGO) | tr A-Z a-z)_final.zip} \
		--algo $(ALGO) --episodes $(EPISODES) --max-steps $(MAX_STEPS) \
		--out $(RESULTS)/rl_eval.json --csv $(RESULTS)/rl_eval.csv

py-random:
	$(PYTHON) -m rl.random_baseline --episodes $(EPISODES) \
		--max-steps $(MAX_STEPS) --seed $(SEED) \
		--out $(RESULTS)/random_eval.json --csv $(RESULTS)/random_eval.csv

py-compare:
	$(PYTHON) -m rl.compare \
		--rl $(RESULTS)/rl_eval.json \
		--random $(RESULTS)/random_eval.json \
		--out-json $(RESULTS)/compare.json \
		--out-csv $(RESULTS)/compare.csv \
		--out-md $(RESULTS)/COMPARISON.md \
		--plot $(RESULTS)/compare.png \
		--horizon $(MAX_STEPS)

py-smoke:
	$(MAKE) py-train ALGO=$(ALGO) STEPS=5000 MAX_STEPS=500
	$(MAKE) py-eval  ALGO=$(ALGO) EPISODES=3 MAX_STEPS=1500
	$(MAKE) py-random EPISODES=3 MAX_STEPS=1500 SEED=1
	$(MAKE) py-compare MAX_STEPS=1500

clean:
	rm -rf $(BUILD_DIR)/simv* $(BUILD_DIR)/*.daidir \
	       $(BUILD_DIR)/csrc $(BUILD_DIR)/ucli.key \
	       $(BUILD_DIR)/*.log $(BUILD_DIR)/*.vcd \
	       $(LOG_DIR)

distclean: clean
	rm -rf models/ $(RESULTS)/rl_eval.* $(RESULTS)/random_eval.* \
	       $(RESULTS)/compare.*
