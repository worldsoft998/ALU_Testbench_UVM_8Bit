// ============================================================================
// alu_rl_test.sv - RL-driven stimulus generation via the PyHDL-IF bridge
// ============================================================================
// The alu_env is built with use_rl=1, so the bridge + alu_rl_sequence take
// over stimulus generation. The test itself just raises an objection until
// the bridge reports end-of-episode or max_items has been reached.
// ============================================================================
`ifndef ALU_RL_TEST_SV
`define ALU_RL_TEST_SV

class alu_rl_test extends alu_base_test;
    `uvm_component_utils(alu_rl_test)

    function new(string name = "alu_rl_test", uvm_component parent = null);
        super.new(name, parent);
        use_rl = 1'b1;
    endfunction

    virtual function void build_phase(uvm_phase phase);
        uvm_config_db#(bit)::set(this, "", "use_rl", 1'b1);
        uvm_config_db#(int unsigned)::set(this, "env.bridge", "max_items", num_items);
        super.build_phase(phase);
    endfunction

    virtual task main_body();
        // The bridge drives the sequencer; just wait for it to finish.
        while (!env.bridge.eo_episode &&
               (env.bridge.max_items == 0 || env.bridge.n_rsp_sent < env.bridge.max_items))
            #100ns;
    endtask
endclass

`endif
