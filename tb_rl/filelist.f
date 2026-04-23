# =============================================================================
# VCS file list for the RL-enabled UVM testbench
# Include paths:
#   +incdir+tb_rl/agents/alu_agent/sequence_items
#   +incdir+tb_rl/agents/alu_agent/sequencer
#   +incdir+tb_rl/agents/alu_agent/driver
#   +incdir+tb_rl/agents/alu_agent/monitor
#   +incdir+tb_rl/agents/alu_agent
#   +incdir+tb_rl/sequences
#   +incdir+tb_rl/scoreboards
#   +incdir+tb_rl/coverage
#   +incdir+tb_rl/bridge
#   +incdir+tb_rl/env
#   +incdir+tb_rl/tests
#   +incdir+tb_rl/pkg
#   +incdir+tb_rl/common
#   +incdir+DUT
# =============================================================================

+incdir+DUT
+incdir+tb_rl/agents/alu_agent/sequence_items
+incdir+tb_rl/agents/alu_agent/sequencer
+incdir+tb_rl/agents/alu_agent/driver
+incdir+tb_rl/agents/alu_agent/monitor
+incdir+tb_rl/agents/alu_agent
+incdir+tb_rl/sequences
+incdir+tb_rl/scoreboards
+incdir+tb_rl/coverage
+incdir+tb_rl/bridge
+incdir+tb_rl/env
+incdir+tb_rl/tests
+incdir+tb_rl/pkg
+incdir+tb_rl/common

# DUT
DUT/ALU_DUT.sv
DUT/ALU_interface.sv

# Bridge interfaces (ties into pyhdl-if fifos)
tb_rl/bridge/alu_bridge_if.sv

# Package (compiles all classes in dependency order)
tb_rl/pkg/alu_tb_pkg.sv

# Top-level module
tb_rl/top/testbench_top.sv
