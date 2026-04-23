// ============================================================================
// alu_base_test.sv - Base test: spins up env, drives reset, overrideable body
// ============================================================================
`ifndef ALU_BASE_TEST_SV
`define ALU_BASE_TEST_SV

class alu_base_test extends uvm_test;
    `uvm_component_utils(alu_base_test)

    alu_env env;
    int unsigned num_items;
    bit          use_rl;

    function new(string name = "alu_base_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        num_items = 1000;
        void'(uvm_config_db#(int unsigned)::get(this, "", "num_items", num_items));
        void'(uvm_config_db#(bit)::get(this, "", "use_rl", use_rl));
        uvm_config_db#(bit)::set(this, "env", "use_rl", use_rl);
        env = alu_env::type_id::create("env", this);
    endfunction

    virtual function void end_of_elaboration_phase(uvm_phase phase);
        super.end_of_elaboration_phase(phase);
        uvm_top.print_topology();
    endfunction

    virtual task main_body();
        // Intentionally empty - overridden by concrete tests.
    endtask

    virtual task run_phase(uvm_phase phase);
        alu_reset_sequence rst_seq;
        super.run_phase(phase);
        phase.raise_objection(this);
        rst_seq = alu_reset_sequence::type_id::create("rst_seq");
        rst_seq.start(env.agent.sqr);
        main_body();
        #500ns;
        phase.drop_objection(this);
    endtask
endclass

`endif
