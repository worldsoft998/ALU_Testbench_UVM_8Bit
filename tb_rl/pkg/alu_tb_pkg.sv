// ============================================================================
// alu_tb_pkg.sv - Package gathering all UVM class declarations in order
// ============================================================================
`ifndef ALU_TB_PKG_SV
`define ALU_TB_PKG_SV

package alu_tb_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // ---- agent core ----
    `include "alu_seq_item.sv"
    `include "alu_sequencer.sv"
    `include "alu_driver.sv"
    `include "alu_monitor.sv"
    `include "alu_agent.sv"

    // ---- sequences ----
    `include "alu_base_sequence.sv"
    `include "alu_reset_sequence.sv"
    `include "alu_random_sequence.sv"
    `include "alu_directed_sequence.sv"

    // ---- analysis components ----
    `include "alu_scoreboard.sv"
    `include "alu_coverage_collector.sv"

    // ---- bridge and RL sequence (forward-decls via typedef) ----
    typedef class alu_rl_sequence;
    `include "alu_rl_bridge.sv"
    `include "alu_rl_sequence.sv"

    // ---- env ----
    `include "alu_env.sv"

    // ---- tests ----
    `include "alu_base_test.sv"
    `include "alu_random_test.sv"
    `include "alu_directed_test.sv"
    `include "alu_rl_test.sv"

endpackage

`endif
