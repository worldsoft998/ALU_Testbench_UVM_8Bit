// ============================================================================
// alu_directed_test.sv - Directed corner cases
// ============================================================================
`ifndef ALU_DIRECTED_TEST_SV
`define ALU_DIRECTED_TEST_SV

class alu_directed_test extends alu_base_test;
    `uvm_component_utils(alu_directed_test)

    function new(string name = "alu_directed_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual task main_body();
        alu_directed_sequence seq;
        seq = alu_directed_sequence::type_id::create("dir");
        seq.start(env.agent.sqr);
    endtask
endclass

`endif
