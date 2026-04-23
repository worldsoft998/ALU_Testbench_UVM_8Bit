// ============================================================================
// alu_base_sequence.sv - Base class for all ALU sequences
// ============================================================================
`ifndef ALU_BASE_SEQUENCE_SV
`define ALU_BASE_SEQUENCE_SV

class alu_base_sequence extends uvm_sequence #(alu_seq_item);
    `uvm_object_utils(alu_base_sequence)

    int unsigned num_items = 100;

    function new(string name = "alu_base_sequence");
        super.new(name);
    endfunction
endclass

`endif
