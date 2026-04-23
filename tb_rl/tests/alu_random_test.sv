// ============================================================================
// alu_random_test.sv - Baseline: pure random stimulus (no RL)
// ============================================================================
`ifndef ALU_RANDOM_TEST_SV
`define ALU_RANDOM_TEST_SV

class alu_random_test extends alu_base_test;
    `uvm_component_utils(alu_random_test)

    function new(string name = "alu_random_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual task main_body();
        alu_random_sequence seq;
        seq = alu_random_sequence::type_id::create("rnd");
        seq.num_items = num_items;
        seq.start(env.agent.sqr);
    endtask
endclass

`endif
