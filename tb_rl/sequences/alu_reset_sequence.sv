// ============================================================================
// alu_reset_sequence.sv - Drives a single reset transaction
// ============================================================================
`ifndef ALU_RESET_SEQUENCE_SV
`define ALU_RESET_SEQUENCE_SV

class alu_reset_sequence extends alu_base_sequence;
    `uvm_object_utils(alu_reset_sequence)

    function new(string name = "alu_reset_sequence");
        super.new(name);
    endfunction

    virtual task body();
        alu_seq_item it;
        it = alu_seq_item::type_id::create("rst_item");
        start_item(it);
        if (!it.randomize() with { Reset == 1'b1; })
            `uvm_error(get_type_name(), "reset randomize failed")
        finish_item(it);
    endtask
endclass

`endif
