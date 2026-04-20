// =============================================================================
// ALU RL-Enhanced Testbench Top Module
// =============================================================================
// Top-level module for RL-guided verification.
// Uses ALU_RL_pkg which includes both standard and RL components.
//
// Plusargs control which test is run:
//   +UVM_TESTNAME=ALU_RL_Test      : RL-guided test
//   +UVM_TESTNAME=ALU_Baseline_Test : Baseline random test
//   +UVM_TESTNAME=ALU_Test          : Original test (80k transactions)
// =============================================================================

import uvm_pkg::*;
`include "ALU_interface.sv"

`include "uvm_macros.svh"
import ALU_RL_pkg::*;

module Top;
    bit CLK;

    ALU_interface intf(.CLK(CLK));

    DUT dut(
        .CLK(CLK),
        .Reset(intf.Reset),
        .A(intf.A),
        .B(intf.B),
        .op_code(intf.op_code),
        .C_in(intf.C_in),
        .Result(intf.Result),
        .C_out(intf.C_out),
        .Z_flag(intf.Z_flag)
    );

    always begin
        #5 CLK = ~CLK;
    end

    initial begin
        string test_name;

        uvm_config_db #(virtual ALU_interface)::set(null, "*", "intf", intf);

        // Allow test selection via plusarg (default to ALU_RL_Test)
        if (!$value$plusargs("UVM_TESTNAME=%s", test_name))
            test_name = "ALU_RL_Test";

        run_test(test_name);
    end
endmodule
