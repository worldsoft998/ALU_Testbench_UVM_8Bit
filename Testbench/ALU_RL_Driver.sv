class ALU_RL_Driver extends ALU_Driver;
`uvm_component_utils(ALU_RL_Driver)

// AI configuration
bit use_ai;
alu_rl_bridge bridge;
ALU_RL_Sequence rl_seq;

// Statistics
integer ai_driven_count;
integer standard_driven_count;

// Callbacks for monitoring
event ai_stimulus_generated;
event ai_stimulus_applied;

function new(string name = "ALU_RL_Driver", uvm_component parent = null);
    super.new(name, parent);
    use_ai = 0;
    ai_driven_count = 0;
    standard_driven_count = 0;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    // Get AI configuration
    if (!uvm_config_db #(bit)::get(this, "", "use_ai", use_ai)) begin
        use_ai = 0;
    end
    
    // Get bridge if AI is enabled
    if (use_ai) begin
        if (!uvm_config_db #(alu_rl_bridge)::get(this, "", "rl_bridge", bridge)) begin
            `uvm_warning(get_type_name(), "RL Bridge not found, falling back to standard mode")
            use_ai = 0;
        end
    end
    
    `uvm_info(get_type_name(), $sformatf("Build phase: AI mode=%0d", use_ai), UVM_MEDIUM)
endfunction

task run_phase(uvm_phase phase);
    super.run_phase(phase);
    
    `uvm_info(get_type_name(), "RL Driver started", UVM_MEDIUM)
    
    forever begin
        item = ALU_Sequence_Item::type_id::create("item");
        seq_item_port.get_next_item(item);
        
        if (use_ai && bridge != null && bridge.is_connected()) begin
            drive_ai(item);
        end else begin
            drive(item);
        end
        
        seq_item_port.item_done();
    end
endtask

// AI-driven stimulus application
virtual task drive_ai(ALU_Sequence_Item item);
    `uvm_info(get_type_name(), $sformatf(
        "AI-driven: A=%0d, B=%0d, op=%0d", item.A, item.B, item.op_code), UVM_HIGH)
    
    // Apply with slight timing adjustment for AI-generated stimuli
    @(intf.CLK);
    intf.Reset <= item.Reset;
    intf.A <= item.A;
    intf.B <= item.B;
    intf.op_code <= item.op_code;
    intf.C_in <= item.C_in;
    
    // Wait for response from bridge
    if (bridge != null) begin
        response_item rsp;
        rsp = bridge.send_stimulus_and_wait(
            item.A, item.B, item.op_code, item.C_in, item.Reset
        );
        
        if (rsp != null && rsp.error) begin
            `uvm_warning(get_type_name(), "AI stimulus generated error response")
        end
    end
    
    ai_driven_count++;
    ->ai_stimulus_applied;
endtask

// Override standard drive for AI-aware timing
virtual task drive(ALU_Sequence_Item item);
    @(intf.CLK);
    intf.Reset <= item.Reset;
    intf.A <= item.A;
    intf.B <= item.B;
    intf.op_code <= item.op_code;
    intf.C_in <= item.C_in;
    
    standard_driven_count++;
endtask

// Get driver statistics
virtual function void get_driver_stats(output driver_stats stats);
    stats.ai_driven = ai_driven_count;
    stats.standard_driven = standard_driven_count;
    stats.ai_percentage = ai_driven_count > 0 ? 
        real'(ai_driven_count) / real'(ai_driven_count + standard_driven_count) * 100.0 : 0.0;
endfunction

endclass : ALU_RL_Driver

// Driver statistics
typedef struct {
    integer ai_driven;
    integer standard_driven;
    real ai_percentage;
} driver_stats;