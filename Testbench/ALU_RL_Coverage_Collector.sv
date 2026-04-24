class ALU_RL_Coverage_Collector extends ALU_Coverage_Collector;
`uvm_component_utils(ALU_RL_Coverage_Collector)

// RL-specific coverage tracking
bit rl_enabled;
real ai_generated_coverage;
real random_generated_coverage;

// Coverage efficiency metrics
real coverage_efficiency;  // Coverage per transaction
real ai_efficiency;
real random_efficiency;

// Transaction tracking
integer ai_transactions;
integer random_transactions;
integer ai_covered_bins;
integer random_covered_bins;

// Coverage history for analysis
real coverage_history[$];
real coverage_rate_history[$];
integer transaction_history[$];

// Export for RL agent
uvm_analysis_port #(coverage_data) rl_coverage_port;

class coverage_data extends uvm_object;
    `uvm_object_utils(coverage_data)
    
    real overall_coverage;
    real ai_coverage;
    real random_coverage;
    integer total_transactions;
    integer ai_transactions;
    integer random_transactions;
    real coverage_rate;
    real efficiency;
    real bin_coverage[12];
    
    function new(string name = "coverage_data");
        super.new(name);
    endfunction
endclass

function new(string name = "ALU_RL_Coverage_Collector", uvm_component parent = null);
    super.new(name, parent);
    rl_enabled = 0;
    ai_generated_coverage = 0.0;
    random_generated_coverage = 0.0;
    ai_transactions = 0;
    random_transactions = 0;
    ai_covered_bins = 0;
    random_covered_bins = 0;
    coverage_efficiency = 0.0;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    rl_coverage_port = new("rl_coverage_port", this);
    
    // Check if RL is enabled
    if (!uvm_config_db #(bit)::get(this, "", "rl_enabled", rl_enabled)) begin
        rl_enabled = 0;
    end
    
    `uvm_info(get_type_name(), $sformatf("RL Coverage Collector built: RL=%0d", rl_enabled), UVM_MEDIUM)
endfunction

function void write(ALU_Sequence_Item t);
    super.write(t);
    
    if (rl_enabled) begin
        // Track coverage for RL feedback
        update_rl_coverage(t);
    end
endfunction

// Update coverage specifically for RL feedback
virtual function void update_rl_coverage(ALU_Sequence_Item t);
    integer prev_bins;
    real coverage_before;
    real coverage_after;
    
    prev_bins = count_covered_bins();
    coverage_before = real'(prev_bins) / 12.0;
    
    // Update based on current transaction
    // (Coverage collection happens in parent class sample())
    
    // Count covered bins after
    update_bin_coverage(t);
    
    // Calculate coverage change
    coverage_after = get_overall_coverage();
    
    // Send to RL port
    send_rl_coverage_data(coverage_before, coverage_after);
    
    // Track history
    coverage_history.push_back(coverage_after);
    if (coverage_history.size() > 10000) begin
        coverage_history.pop_front();
    end
    
    // Calculate efficiency
    if (transaction_count > 0) begin
        coverage_rate_history.push_back(coverage_after / real'(transaction_count));
    end
endfunction

// Update individual bin coverage
virtual function void update_bin_coverage(ALU_Sequence_Item t);
    // This would track which bins are covered by AI vs random generation
    // For now, update basic tracking
endfunction

// Count covered bins
virtual function integer count_covered_bins();
    integer count = 0;
    
    // Count covered op_codes
    for (int i = 0; i < 6; i++) begin
        if (op_code_bins[i]) count++;
    end
    
    // Add corner case coverage
    // (simplified - actual implementation depends on covergroup bins)
    
    return count;
endfunction

// Get overall coverage
virtual function real get_overall_coverage();
    integer total_bins = 12;
    integer covered_bins = count_covered_bins();
    return real'(covered_bins) / real'(total_bins);
endfunction

// Send coverage data to RL agent
virtual function void send_rl_coverage_data(real coverage_before, real coverage_after);
    coverage_data cov_data;
    
    cov_data = coverage_data::type_id::create("cov_data");
    cov_data.overall_coverage = coverage_after;
    cov_data.ai_coverage = ai_generated_coverage;
    cov_data.random_coverage = random_generated_coverage;
    cov_data.total_transactions = transaction_count;
    cov_data.ai_transactions = ai_transactions;
    cov_data.random_transactions = random_transactions;
    cov_data.coverage_rate = (coverage_after - coverage_before);
    cov_data.efficiency = calculate_efficiency();
    
    rl_coverage_port.write(cov_data);
endfunction

// Calculate coverage efficiency
virtual function real calculate_efficiency();
    if (transaction_count == 0) return 0.0;
    return real'(get_overall_coverage() * 1000) / real'(transaction_count);
endfunction

// Get RL-specific coverage report
virtual function string get_rl_coverage_report();
    string report;
    
    report = {"\n", "=", "=", "=", "=", "RL Coverage Report", "=", "=", "=", "=", "\n"};
    report = {report, $sformatf("Overall Coverage: %0d%%\n", $rtoi(get_overall_coverage()*100))};
    report = {report, $sformatf("Total Transactions: %0d\n", transaction_count)};
    report = {report, $sformatf("Coverage Efficiency: %f\n", calculate_efficiency())};
    report = {report, "\n"};
    
    report = {report, "Per-Operation Coverage:\n"};
    for (int i = 0; i < 6; i++) begin
        report = {report, $sformatf("  Op %0d: %s\n", i, op_code_bins[i] ? "COVERED" : "NOT COVERED")};
    end
    
    return report;
endfunction

// Get coverage data for RL agent
virtual function real get_coverage_vector()[12];
    real coverage_vec[12];
    
    coverage_vec[0] = get_overall_coverage();
    
    // Operation code coverage
    for (int i = 0; i < 6; i++) begin
        coverage_vec[i+1] = op_code_bins[i] ? 1.0 : 0.0;
    end
    
    // Corner case coverage (simplified)
    coverage_vec[7] = corner_case_covered[0] ? 1.0 : 0.0;
    coverage_vec[8] = corner_case_covered[1] ? 1.0 : 0.0;
    coverage_vec[9] = corner_case_covered[2] ? 1.0 : 0.0;
    coverage_vec[10] = corner_case_covered[3] ? 1.0 : 0.0;
    coverage_vec[11] = corner_case_covered[4] ? 1.0 : 0.0;
    
    return coverage_vec;
endfunction

// Export coverage for external use
virtual function void export_coverage(output coverage_export exp);
    exp.overall = get_overall_coverage();
    exp.ai_coverage = ai_generated_coverage;
    exp.random_coverage = random_generated_coverage;
    exp.efficiency = calculate_efficiency();
    exp.vector = get_coverage_vector();
endfunction

endclass : ALU_RL_Coverage_Collector

// Coverage export structure for RL agent
typedef struct {
    real overall;
    real ai_coverage;
    real random_coverage;
    real efficiency;
    real vector[12];
} coverage_export;

// Coverage bin tracking
class coverage_bin_tracker;
    bit covered;
    integer hit_count;
    integer ai_hit_count;
    integer random_hit_count;
    
    function new();
        covered = 0;
        hit_count = 0;
        ai_hit_count = 0;
        random_hit_count = 0;
    endfunction
    
    function void mark_hit(bit is_ai);
        hit_count++;
        covered = 1;
        if (is_ai) begin
            ai_hit_count++;
        end else begin
            random_hit_count++;
        end
    endfunction
endclass