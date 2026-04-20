// =============================================================================
// RL-Guided Sequence
// =============================================================================
// Reads stimulus values from the PyHDL-IF bridge (file or named pipe)
// instead of using constrained-random generation.
// Falls back to random if bridge is unavailable.
// =============================================================================

class rl_sequence extends base_sequence;

    `uvm_object_utils(rl_sequence)

    pyhdl_if_bridge bridge;
    ALU_Sequence_Item rl_item;
    bit bridge_connected;

    function new(string name = "rl_sequence");
        super.new(name);
        `uvm_info(get_type_name(), "in constructor of rl_sequence", UVM_HIGH)
        bridge_connected = 0;
    endfunction

    // Set the bridge handle (called from test before sequence start)
    function void set_bridge(pyhdl_if_bridge b);
        bridge = b;
        bridge_connected = (b != null) && b.is_connected;
    endfunction

    task body();
        rl_item = ALU_Sequence_Item::type_id::create("rl_item");

        if (bridge != null && bridge.is_connected) begin
            // Read stimulus from bridge
            if (bridge.read_stimulus()) begin
                start_item(rl_item);

                // Override randomization with bridge values
                rl_item.A       = bridge.stim_A;
                rl_item.B       = bridge.stim_B;
                rl_item.op_code = bridge.stim_op_code;
                rl_item.C_in    = bridge.stim_C_in;
                rl_item.Reset   = bridge.stim_reset;

                finish_item(rl_item);

                `uvm_info(get_type_name(), $sformatf(
                    "RL stimulus [%0d]: A=0x%02h B=0x%02h op=%0d C_in=%0b rst=%0b",
                    bridge.seq_id, rl_item.A, rl_item.B, rl_item.op_code,
                    rl_item.C_in, rl_item.Reset), UVM_HIGH)
            end else begin
                `uvm_info(get_type_name(), "Bridge: no more stimuli (DONE)", UVM_LOW)
            end
        end else begin
            // Fallback: constrained random
            start_item(rl_item);
            if (!(rl_item.randomize() with {Reset == 0;})) begin
                `uvm_error(get_type_name(), "Failed to randomize rl_item (fallback)")
            end
            finish_item(rl_item);
        end
    endtask : body

endclass : rl_sequence


// =============================================================================
// RL Batch Sequence - reads all stimuli from file
// =============================================================================
class rl_batch_sequence extends base_sequence;

    `uvm_object_utils(rl_batch_sequence)

    pyhdl_if_bridge bridge;
    int max_transactions;

    function new(string name = "rl_batch_sequence");
        super.new(name);
        max_transactions = 1000;
        `uvm_info(get_type_name(), "in constructor of rl_batch_sequence", UVM_HIGH)
    endfunction

    function void set_bridge(pyhdl_if_bridge b);
        bridge = b;
    endfunction

    function void set_max_transactions(int n);
        max_transactions = n;
    endfunction

    task body();
        ALU_Sequence_Item item;
        int count = 0;

        if (bridge == null || !bridge.is_connected) begin
            `uvm_error(get_type_name(), "Bridge not connected, cannot run batch sequence")
            return;
        end

        `uvm_info(get_type_name(), $sformatf(
            "Starting RL batch sequence (max %0d transactions)", max_transactions), UVM_LOW)

        while (bridge.has_more() && count < max_transactions) begin
            if (!bridge.read_stimulus()) break;

            item = ALU_Sequence_Item::type_id::create($sformatf("rl_item_%0d", count));
            start_item(item);

            item.A       = bridge.stim_A;
            item.B       = bridge.stim_B;
            item.op_code = bridge.stim_op_code;
            item.C_in    = bridge.stim_C_in;
            item.Reset   = bridge.stim_reset;

            finish_item(item);
            count++;
        end

        `uvm_info(get_type_name(), $sformatf(
            "RL batch sequence complete: %0d transactions", count), UVM_LOW)
    endtask : body

endclass : rl_batch_sequence
