class ALU_RL_Env extends ALU_Env;
`uvm_component_utils(ALU_RL_Env)

// RL Components
ALU_RL_Agent rl_agt;
ALU_RL_Coverage_Collector rl_cvcl;
ALU_RL_Scoreboard rl_scb;
alu_rl_bridge rl_bridge;

// Configuration
bit use_ai;
string rl_algorithm;
real coverage_target;
integer max_transactions;

// Statistics tracking
integer ai_transactions;
integer random_transactions;
real total_coverage;
real max_coverage_reached;
real avg_reward;

// Export port for RL data
uvm_analysis_port #(env_statistics) rl_stats_port;

class env_statistics extends uvm_object;
    `uvm_object_utils(env_statistics)
    
    real coverage;
    integer transactions;
    integer ai_transactions;
    integer random_transactions;
    real efficiency;
    real coverage_rate;
    
    function new(string name = "env_statistics");
        super.new(name);
    endfunction
endclass

function new(string name = "ALU_RL_Env", uvm_component parent = null);
    super.new(name, parent);
    use_ai = 0;
    rl_algorithm = "ppo";
    coverage_target = 0.95;
    max_transactions = 100000;
    ai_transactions = 0;
    random_transactions = 0;
    total_coverage = 0.0;
    max_coverage_reached = 0.0;
    avg_reward = 0.0;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    // Get RL configuration from config_db
    if (!uvm_config_db #(bit)::get(this, "", "use_ai", use_ai)) begin
        use_ai = 0;
    end
    
    if (!uvm_config_db #(string)::get(this, "", "rl_algorithm", rl_algorithm)) begin
        rl_algorithm = "ppo";
    end
    
    if (!uvm_config_db #(real)::get(this, "", "coverage_target", coverage_target)) begin
        coverage_target = 0.95;
    end
    
    if (!uvm_config_db #(integer)::get(this, "", "max_transactions", max_transactions)) begin
        max_transactions = 100000;
    end
    
    `uvm_info(get_type_name(), $sformatf(
        "RL Environment build: AI=%0d, Algorithm=%s, Coverage Target=%.0f%%",
        use_ai, rl_algorithm, coverage_target*100), UVM_MEDIUM)
    
    if (use_ai) begin
        // Create RL components
        rl_agt = ALU_RL_Agent::type_id::create("rl_agt", this);
        rl_cvcl = ALU_RL_Coverage_Collector::type_id::create("rl_cvcl", this);
        rl_scb = ALU_RL_Scoreboard::type_id::create("rl_scb", this);
        rl_bridge = alu_rl_bridge::type_id::create("rl_bridge", this);
        
        // Configure RL components
        uvm_config_db #(bit)::set(this, "rl_agt", "use_ai", 1);
        uvm_config_db #(bit)::set(this, "rl_cvcl", "rl_enabled", 1);
        uvm_config_db #(bit)::set(this, "rl_scb", "rl_enabled", 1);
    end
    
    // Create stats port
    rl_stats_port = new("rl_stats_port", this);
endfunction

function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    
    if (use_ai) begin
        // Connect RL components
        if (rl_cvcl != null) begin
            alu_agt.alu_mon.monitor_port.connect(rl_cvcl.rl_coverage_port);
        end
        
        `uvm_info(get_type_name(), "RL Environment connected", UVM_MEDIUM)
    end
endfunction

task run_phase(uvm_phase phase);
    real current_coverage;
    real start_time;
    real elapsed;
    
    super.run_phase(phase);
    
    `uvm_info(get_type_name(), "RL Environment run phase started", UVM_MEDIUM)
    
    start_time = $realtime;
    
    if (use_ai) begin
        `uvm_info(get_type_name(), "Running in AI-assisted mode", UVM_MEDIUM)
        
        // Monitor coverage progress
        forever begin
            #1000; // Check every 1000 time units
            
            if (rl_cvcl != null) begin
                current_coverage = rl_cvcl.get_overall_coverage();
                
                if (current_coverage > max_coverage_reached) begin
                    max_coverage_reached = current_coverage;
                end
                
                // Send statistics
                send_env_statistics(current_coverage);
                
                // Check if target reached
                if (current_coverage >= coverage_target) begin
                    `uvm_info(get_type_name(), $sformatf(
                        "Coverage target %.0f%% reached!", coverage_target*100), UVM_MEDIUM)
                    break;
                end
            end
            
            elapsed = $realtime - start_time;
            if (elapsed > max_transactions * 10) begin // Rough time estimate
                `uvm_warning(get_type_name(), "Max simulation time approaching")
                break;
            end
        end
    end else begin
        `uvm_info(get_type_name(), "Running in standard mode", UVM_MEDIUM)
    end
endtask

// Send environment statistics
virtual function void send_env_statistics(real coverage);
    env_statistics stats;
    
    stats = env_statistics::type_id::create("stats");
    stats.coverage = coverage;
    stats.transactions = alu_agt.alu_mon.transaction_count;
    stats.ai_transactions = ai_transactions;
    stats.random_transactions = random_transactions;
    stats.efficiency = calculate_efficiency(coverage, stats.transactions);
    stats.coverage_rate = coverage - total_coverage;
    
    total_coverage = coverage;
    
    rl_stats_port.write(stats);
endfunction

// Calculate coverage efficiency
virtual function real calculate_efficiency(real coverage, integer transactions);
    if (transactions == 0) return 0.0;
    return (coverage * 1000.0) / real'(transactions);
endfunction

// Get RL environment report
virtual function string get_rl_env_report();
    string report;
    
    report = {"\n", "=", "=", "=", "=", "RL Environment Report", "=", "=", "=", "=", "\n"};
    report = {report, $sformatf("AI Mode: %s\n", use_ai ? "ENABLED" : "DISABLED")};
    report = {report, $sformatf("Algorithm: %s\n", rl_algorithm)};
    report = {report, $sformatf("Coverage Target: %.0f%%\n", coverage_target*100)};
    report = {report, $sformatf("Max Transactions: %0d\n", max_transactions)};
    report = {report, "\n"};
    
    if (rl_cvcl != null) begin
        report = {report, rl_cvcl.get_rl_coverage_report()};
    end
    
    if (rl_scb != null) begin
        report = {report, rl_scb.get_rl_scoreboard_report()};
    end
    
    return report;
endfunction

// Export environment data
virtual function void export_env_data(output env_export exp);
    exp.use_ai = use_ai;
    exp.algorithm = rl_algorithm;
    exp.target_coverage = coverage_target;
    exp.max_transactions = max_transactions;
    exp.current_coverage = rl_cvcl != null ? rl_cvcl.get_overall_coverage() : 0.0;
    exp.max_coverage = max_coverage_reached;
    exp.efficiency = calculate_efficiency(max_coverage_reached, max_transactions);
endfunction

endclass : ALU_RL_Env

// Environment export for RL
typedef struct {
    bit use_ai;
    string algorithm;
    real target_coverage;
    integer max_transactions;
    real current_coverage;
    real max_coverage;
    real efficiency;
} env_export;