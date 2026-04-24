class ALU_RL_Agent extends ALU_Agent;
`uvm_component_utils(ALU_RL_Agent)

// RL Components
ALU_RL_Driver rl_driver;
alu_rl_bridge rl_bridge;

// Configuration
bit use_ai;
bit bridge_connected;

// Statistics
integer ai_driven_count;
integer standard_driven_count;

function new(string name = "ALU_RL_Agent", uvm_component parent = null);
    super.new(name, parent);
    use_ai = 0;
    bridge_connected = 0;
    ai_driven_count = 0;
    standard_driven_count = 0;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    // Get AI configuration
    if (!uvm_config_db #(bit)::get(this, "", "use_ai", use_ai)) begin
        use_ai = 0;
    end
    
    `uvm_info(get_type_name(), $sformatf("RL Agent build: AI=%0d", use_ai), UVM_MEDIUM)
    
    if (use_ai) begin
        // Create RL bridge
        rl_bridge = alu_rl_bridge::type_id::create("rl_bridge", this);
        
        // Override driver with RL driver
        alu_driver = ALU_RL_Driver::type_id::create("ALU_RL_Driver", this);
        rl_driver = ALU_RL_Driver::type_id::get();
        
        // Configure driver for AI mode
        uvm_config_db #(bit)::set(this, "ALU_RL_Driver", "use_ai", 1);
        uvm_config_db #(alu_rl_bridge)::set(this, "ALU_RL_Driver", "rl_bridge", rl_bridge);
    end
endfunction

function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    
    if (use_ai && rl_bridge != null) begin
        // Connect bridge
        bridge_connected = (rl_bridge.connect() == 0);
        
        if (bridge_connected) begin
            `uvm_info(get_type_name(), "RL Bridge connected successfully", UVM_MEDIUM)
        end else begin
            `uvm_warning(get_type_name(), "Failed to connect RL Bridge")
        end
    end
    
    // Connect RL components
    if (rl_driver != null) begin
        rl_driver.intf = this.intf;
    end
endfunction

task run_phase(uvm_phase phase);
    super.run_phase(phase);
    
    if (use_ai) begin
        `uvm_info(get_type_name(), "RL Agent running in AI mode", UVM_MEDIUM)
    end else begin
        `uvm_info(get_type_name(), "RL Agent running in standard mode", UVM_MEDIUM)
    end
endtask

// Connect bridge to sequence
function void connect_bridge_to_sequence(alu_rl_sequence seq);
    if (rl_bridge != null) begin
        seq.bridge = rl_bridge;
        `uvm_info(get_type_name(), "Bridge connected to sequence", UVM_MEDIUM)
    end
endfunction

// Get RL statistics
function void get_rl_agent_stats(output rl_agent_stats stats);
    if (rl_driver != null) begin
        rl_driver.get_driver_stats(stats.driver_stats);
    end else begin
        stats.driver_stats.ai_driven = 0;
        stats.driver_stats.standard_driven = 0;
        stats.driver_stats.ai_percentage = 0.0;
    end
    
    stats.ai_mode = use_ai;
    stats.bridge_connected = bridge_connected;
    
    if (rl_bridge != null) begin
        rl_bridge.get_statistics(stats.bridge_stats);
    end
endfunction

// Disconnect bridge
function void disconnect_bridge();
    if (rl_bridge != null && bridge_connected) begin
        rl_bridge.disconnect();
        bridge_connected = 0;
        `uvm_info(get_type_name(), "Bridge disconnected", UVM_MEDIUM)
    end
endfunction

endclass : ALU_RL_Agent

// RL Agent statistics
typedef struct {
    driver_stats driver_stats;
    bit ai_mode;
    bit bridge_connected;
    bridge_statistics bridge_stats;
} rl_agent_stats;