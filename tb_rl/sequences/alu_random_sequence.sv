// ============================================================================
// alu_random_sequence.sv - Pure-random stimulus (baseline for RL comparison)
// ============================================================================
`ifndef ALU_RANDOM_SEQUENCE_SV
`define ALU_RANDOM_SEQUENCE_SV

class alu_random_sequence extends alu_base_sequence;
    `uvm_object_utils(alu_random_sequence)

    function new(string name = "alu_random_sequence");
        super.new(name);
    endfunction

    virtual task body();
        alu_seq_item it;
        for (int i = 0; i < num_items; i++) begin
            it = alu_seq_item::type_id::create($sformatf("rnd_%0d", i));
            start_item(it);
            if (!it.randomize() with { Reset == 1'b0; })
                `uvm_error(get_type_name(), "random randomize failed")
            finish_item(it);
        end
    endtask
endclass

`endif
