// ============================================================================
// alu_directed_sequence.sv - Directed corner-case sequence
// ============================================================================
// Hits every op_code with the four canonical corner pairs (0,0)(0,FF)
// (FF,0)(FF,FF). Useful as a sanity baseline and as the "teacher" that RL
// must match-or-beat with stimulus optimisation.
// ============================================================================
`ifndef ALU_DIRECTED_SEQUENCE_SV
`define ALU_DIRECTED_SEQUENCE_SV

class alu_directed_sequence extends alu_base_sequence;
    `uvm_object_utils(alu_directed_sequence)

    function new(string name = "alu_directed_sequence");
        super.new(name);
    endfunction

    virtual task body();
        alu_seq_item it;
        bit [7:0] corners[4] = '{8'h00, 8'h00, 8'hFF, 8'hFF};
        bit [7:0] corners_b[4] = '{8'h00, 8'hFF, 8'h00, 8'hFF};
        for (int op = 0; op < 6; op++) begin
            for (int i = 0; i < 4; i++) begin
                it = alu_seq_item::type_id::create($sformatf("dir_%0d_%0d", op, i));
                start_item(it);
                it.Reset   = 1'b0;
                it.op_code = op[3:0];
                it.A       = corners[i];
                it.B       = corners_b[i];
                it.C_in    = i[0];
                finish_item(it);
            end
        end
    endtask
endclass

`endif
