// ============================================================================
// testbench_top.sv - RL-enabled UVM testbench top for Synopsys VCS
// ============================================================================
// * Reuses the existing DUT and ALU_interface from DUT/ unchanged.
// * Adds two PyHDL-IF-backed bridge interfaces for the 2-way bridge.
// * Selects the UVM test at runtime via +UVM_TESTNAME=<test> (see Makefile).
// ============================================================================
`timescale 1ns/1ps

`include "uvm_macros.svh"
`include "ALU_interface.sv"
`include "alu_bridge_if.sv"

module testbench_top;
    import uvm_pkg::*;
    import alu_tb_pkg::*;

    // Clock & reset generation ------------------------------------------------
    logic CLK;
    logic RST_BRG;
    initial CLK = 0;
    always #5 CLK = ~CLK;           // 100 MHz

    // Short bridge-reset pulse; the UVM driver handles DUT reset separately.
    initial begin
        RST_BRG = 1'b1;
        #30 RST_BRG = 1'b0;
    end

    // DUT --------------------------------------------------------------------
    ALU_interface intf(.CLK(CLK));

    DUT dut(
        .CLK    (CLK),
        .Reset  (intf.Reset),
        .A      (intf.A),
        .B      (intf.B),
        .op_code(intf.op_code),
        .C_in   (intf.C_in),
        .Result (intf.Result),
        .C_out  (intf.C_out),
        .Z_flag (intf.Z_flag)
    );

    // Bridge interfaces (only active when +USE_RL=1 is passed) ---------------
    alu_req_if req_if(.clk(CLK), .rst(RST_BRG));
    alu_rsp_if rsp_if(.clk(CLK), .rst(RST_BRG));

    // UVM configuration ------------------------------------------------------
    initial begin
        int unsigned ni;
        bit          rl_on;
        string       algo;
        int          seed_val;

        ni       = 1000;
        rl_on    = 1'b0;
        algo     = "PPO";
        seed_val = 0;

        void'($value$plusargs("NUM_ITEMS=%d", ni));
        void'($value$plusargs("USE_RL=%d",    rl_on));
        void'($value$plusargs("ALGO=%s",      algo));
        void'($value$plusargs("SEED=%d",      seed_val));

        uvm_config_db#(virtual ALU_interface)::set(null, "*", "intf",    intf);
        uvm_config_db#(virtual alu_req_if)  ::set(null, "*", "req_vif", req_if);
        uvm_config_db#(virtual alu_rsp_if)  ::set(null, "*", "rsp_vif", rsp_if);
        uvm_config_db#(int unsigned)        ::set(null, "uvm_test_top", "num_items", ni);
        uvm_config_db#(bit)                 ::set(null, "uvm_test_top", "use_rl",    rl_on);

        if (seed_val != 0)
            $srandom(seed_val);

        $display("[tb] testbench_top: USE_RL=%0d NUM_ITEMS=%0d ALGO=%s SEED=%0d",
                 rl_on, ni, algo, seed_val);
        run_test();
    end

    // Simulation-time safety net (overridable via +TIMEOUT_NS=xxxx) ----------
    initial begin
        int unsigned timeout_ns;
        timeout_ns = 5_000_000;
        void'($value$plusargs("TIMEOUT_NS=%d", timeout_ns));
        #(timeout_ns);
        `uvm_fatal("TB_TOP", $sformatf("simulation timed out after %0d ns", timeout_ns))
    end

    // Waveforms --------------------------------------------------------------
    initial begin
        if ($test$plusargs("DUMP")) begin
            $dumpfile("waves.vcd");
            $dumpvars(0, testbench_top);
        end
    end
endmodule
