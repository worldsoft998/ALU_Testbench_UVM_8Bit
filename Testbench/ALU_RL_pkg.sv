// =============================================================================
// ALU RL-Enhanced Package
// =============================================================================
// Extended package that includes both the original UVM components
// and the RL bridge + RL-guided sequences/tests.
//
// Use this package when compiling with RL support enabled.
// The original ALU_pkg.sv remains untouched for non-RL builds.
// =============================================================================

package ALU_RL_pkg;
    import uvm_pkg::*;

    `include "uvm_macros.svh"

    // ---------- Original components (same include order as ALU_pkg) ----------
    `include "ALU_Sequence_Item.sv"
    `include "ALU_Sequence.sv"
    `include "ALU_Sequencer.sv"
    `include "ALU_Driver.sv"
    `include "ALU_monitor.sv"
    `include "ALU_Coverage_Collector.sv"
    `include "ALU_Scoreboard.sv"
    `include "ALU_Agent.sv"
    `include "ALU_Env.sv"
    `include "Test.sv"

    // ---------- RL Bridge ----------
    `include "pyhdl_if_bridge.sv"

    // ---------- RL Sequences ----------
    `include "ALU_RL_Sequence.sv"

    // ---------- RL Tests ----------
    `include "ALU_RL_Test.sv"

endpackage : ALU_RL_pkg
