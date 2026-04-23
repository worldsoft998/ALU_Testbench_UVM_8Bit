// ============================================================================
// alu_rl_sequence.sv - UVM sequence that converts bridge requests to items
// ============================================================================
// Pulls packed 64-bit requests from the alu_rl_bridge's TLM input FIFO and
// starts a sequence item for each one. On timeout (handled inside the bridge)
// the sequence self-generates a randomised item so the simulation keeps
// progressing and the RL episode is not wasted.
// ============================================================================
`ifndef ALU_RL_SEQUENCE_SV
`define ALU_RL_SEQUENCE_SV

class alu_rl_sequence extends uvm_sequence #(alu_seq_item);
    `uvm_object_utils(alu_rl_sequence)

    alu_rl_bridge bridge;
    int unsigned  max_items;

    function new(string name = "alu_rl_sequence");
        super.new(name);
    endfunction

    virtual task body();
        alu_seq_item it;
        bit [63:0]   payload;
        bit          got;
        bit          reset_b;
        bit          cin_b;
        bit [3:0]    op;
        bit [7:0]    a;
        bit [7:0]    b;
        bit          eoe;
        int          gid;
        int unsigned count;

        count      = 0;
        max_items  = (bridge != null) ? bridge.max_items : 0;

        forever begin
            if (max_items != 0 && count >= max_items)
                break;

            bridge.get_request(payload, got);
            it = alu_seq_item::type_id::create("rl_it");

            if (got) begin
                bridge.unpack_request(payload, reset_b, cin_b, op, a, b, eoe, gid);
                if (eoe) begin
                    `uvm_info(get_type_name(), "end-of-episode received", UVM_LOW)
                    bridge.eo_episode = 1'b1;
                    break;
                end
                start_item(it);
                it.Reset    = reset_b;
                it.C_in     = cin_b;
                it.op_code  = op;
                it.A        = a;
                it.B        = b;
                it.from_rl  = 1'b1;
                it.gen_id   = gid;
                finish_item(it);
            end else begin
                // Timeout fallback - randomise so we still accumulate coverage.
                start_item(it);
                if (!it.randomize() with { Reset == 1'b0; })
                    `uvm_error(get_type_name(), "fallback randomize failed")
                it.from_rl = 1'b0;
                it.gen_id  = -1;
                finish_item(it);
            end
            count++;
        end
    endtask
endclass

`endif
