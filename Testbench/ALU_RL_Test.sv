class ALU_RL_Test extends ALU_Test;
`uvm_component_utils(ALU_RL_Test)

// RL Configuration
bit use_ai;
string rl_algorithm;
integer num_transactions;
real coverage_target;
string python_host;
integer python_port;

// Sequences
alu_rl_sequence rl_seq;

// Comparison tracking
integer baseline_transactions;
integer ai_transactions;
real baseline_coverage;
real ai_coverage;
real baseline_time;
real ai_time;

// Report tracking
string baseline_report;
string ai_report;

function new(string name = "ALU_RL_Test", uvm_component parent = null);
    super.new(name, parent);
    use_ai = 0;
    rl_algorithm = "ppo";
    num_transactions = 100000;
    coverage_target = 0.95;
    python_host = "localhost";
    python_port = 5555;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    // Get configuration from command line or defaults
    if (!$value$plusargs("USE_AI=%d", use_ai)) begin
        use_ai = 0;
    end
    
    if (!$value$plusargs("RL_ALGORITHM=%s", rl_algorithm)) begin
        rl_algorithm = "ppo";
    end
    
    if (!$value$plusargs("NUM_TRANSACTIONS=%d", num_transactions)) begin
        num_transactions = 100000;
    end
    
    if (!$value$plusargs("COVERAGE_TARGET=%f", coverage_target)) begin
        coverage_target = 0.95;
    end
    
    if (!$value$plusargs("PYTHON_HOST=%s", python_host)) begin
        python_host = "localhost";
    end
    
    if (!$value$plusargs("PYTHON_PORT=%d", python_port)) begin
        python_port = 5555;
    end
    
    // Set configuration in config_db
    uvm_config_db #(bit)::set(this, "env", "use_ai", use_ai);
    uvm_config_db #(string)::set(this, "env", "rl_algorithm", rl_algorithm);
    uvm_config_db #(real)::set(this, "env", "coverage_target", coverage_target);
    uvm_config_db #(integer)::set(this, "env", "max_transactions", num_transactions);
    
    // Recreate environment with RL if AI is enabled
    if (use_ai) begin
        `uvm_info(get_type_name(), "Creating RL Environment", UVM_MEDIUM)
        env = ALU_RL_Env::type_id::create("env", this);
    end
    
    `uvm_info(get_type_name(), $sformatf(
        "Test Configuration:\n  AI: %0d\n  Algorithm: %s\n  Transactions: %0d\n  Coverage Target: %.0f%%",
        use_ai, rl_algorithm, num_transactions, coverage_target*100), UVM_MEDIUM)
endfunction

task run_phase(uvm_phase phase);
    real start_time;
    real end_time;
    
    super.run_phase(phase);
    
    `uvm_info(get_type_name(), "=", "=", 70)
    `uvm_info(get_type_name(), "Starting ALU RL Test", UVM_MEDIUM)
    `uvm_info(get_type_name(), "=", "=", 70)
    
    start_time = $realtime;
    
    phase.raise_objection(this);
    
    if (use_ai) begin
        // Run AI-assisted test
        run_ai_test(phase);
    end else begin
        // Run baseline test
        run_baseline_test(phase);
    end
    
    end_time = $realtime;
    
    phase.drop_objection(this);
    
    `uvm_info(get_type_name(), "=", "=", 70)
    `uvm_info(get_type_name(), "Test Completed", UVM_MEDIUM)
    `uvm_info(get_type_name(), "=", "=", 70)
    
    // Print final report
    print_test_report();
endtask

// Run baseline (non-AI) test
virtual task run_baseline_test(uvm_phase phase);
    test_sequence baseline_seq;
    integer txn_count;
    
    `uvm_info(get_type_name(), "Running BASELINE Test (no AI)", UVM_MEDIUM)
    
    baseline_time = $realtime;
    
    // Reset sequence
    rst_seq = rst_sequence::type_id::create("rst_seq");
    rst_seq.start(env.alu_agt.alu_sequencer);
    #100;
    
    // Run baseline transactions
    baseline_seq = test_sequence::type_id::create("baseline_seq");
    
    for (int i = 0; i < num_transactions; i++) begin
        #20;
        baseline_seq = test_sequence::type_id::create($sformatf("baseline_seq_%0d", i));
        baseline_seq.start(env.alu_agt.alu_sequencer);
        baseline_transactions++;
        
        // Check coverage
        if (env.alu_cvcl != null) begin
            baseline_coverage = env.alu_cvcl.get_overall_coverage();
            if (baseline_coverage >= coverage_target) begin
                `uvm_info(get_type_name(), $sformatf(
                    "Baseline: Coverage target reached at transaction %0d", i), UVM_MEDIUM)
                break;
            end
        end
        
        if (i % 10000 == 0) begin
            `uvm_info(get_type_name(), $sformatf(
                "Baseline Progress: %0d/%0d transactions, Coverage: %.0f%%",
                i, num_transactions, baseline_coverage*100), UVM_MEDIUM)
        end
    end
    
    baseline_time = $realtime - baseline_time;
    
    `uvm_info(get_type_name(), $sformatf(
        "Baseline Test Complete: %0d transactions in %0t, Coverage: %.0f%%",
        baseline_transactions, baseline_time, baseline_coverage*100), UVM_MEDIUM)
endtask

// Run AI-assisted test
virtual task run_ai_test(uvm_phase phase);
    ALU_RL_Env rl_env;
    
    `uvm_info(get_type_name(), $sformatf("Running AI Test with %s", rl_algorithm), UVM_MEDIUM)
    
    ai_time = $realtime;
    
    // Cast environment to RL environment
    if (!$cast(rl_env, env)) begin
        `uvm_error(get_type_name(), "Failed to cast to RL environment")
        return;
    end
    
    // Reset
    rst_seq = rst_sequence::type_id::create("rst_seq");
    rst_seq.start(env.alu_agt.alu_sequencer);
    #100;
    
    // Create and start RL sequence
    rl_seq = alu_rl_sequence::type_id::create("rl_seq");
    rl_seq.use_ai_generation = 1;
    rl_seq.num_transactions = num_transactions;
    rl_seq.target_coverage = coverage_target;
    rl_seq.bridge = rl_env.rl_bridge;
    
    // Start sequence
    fork
        rl_seq.start(env.alu_agt.alu_sequencer);
    join
    
    ai_transactions = rl_seq.transactions_completed;
    ai_coverage = rl_seq.current_coverage;
    
    ai_time = $realtime - ai_time;
    
    `uvm_info(get_type_name(), $sformatf(
        "AI Test Complete: %0d transactions in %0t, Coverage: %.0f%%",
        ai_transactions, ai_time, ai_coverage*100), UVM_MEDIUM)
endtask

// Print comparison report
virtual function void print_test_report();
    real time_improvement;
    real txn_improvement;
    real coverage_delta;
    
    `uvm_info(get_type_name(), "\n", UVM_MEDIUM)
    `uvm_info(get_type_name(), "=", "=", 70)
    `uvm_info(get_type_name(), "FINAL TEST REPORT", UVM_MEDIUM)
    `uvm_info(get_type_name(), "=", "=", 70)
    
    if (use_ai) begin
        print_ai_comparison_report();
    end else begin
        print_baseline_report();
    end
endfunction

// Print baseline report
virtual function void print_baseline_report();
    `uvm_info(get_type_name(), "BASELINE CONFIGURATION", UVM_MEDIUM)
    `uvm_info(get_type_name(), "-", "=", 70)
    `uvm_info(get_type_name(), $sformatf("Algorithm: Random (Baseline)"), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("Transactions: %0d", baseline_transactions), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("Coverage: %.0f%%", baseline_coverage*100), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("Time: %0t", baseline_time), UVM_MEDIUM)
endfunction

// Print AI comparison report
virtual function void print_ai_comparison_report();
    real time_improvement;
    real txn_improvement;
    real coverage_delta;
    
    `uvm_info(get_type_name(), "BASELINE vs AI COMPARISON", UVM_MEDIUM)
    `uvm_info(get_type_name(), "-", "=", 70)
    
    `uvm_info(get_type_name(), "Baseline Configuration:", UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Algorithm: Random (No AI)"), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Transactions: %0d", baseline_transactions), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Coverage: %.0f%%", baseline_coverage*100), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Time: %0t", baseline_time), UVM_MEDIUM)
    
    `uvm_info(get_type_name(), "", UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("AI-Assisted Configuration:"), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Algorithm: %s", rl_algorithm), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Transactions: %0d", ai_transactions), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Coverage: %.0f%%", ai_coverage*100), UVM_MEDIUM)
    `uvm_info(get_type_name(), $sformatf("  Time: %0t", ai_time), UVM_MEDIUM)
    
    // Calculate improvements
    `uvm_info(get_type_name(), "", UVM_MEDIUM)
    `uvm_info(get_type_name(), "IMPROVEMENTS:", UVM_MEDIUM)
    
    if (baseline_transactions > 0) begin
        txn_improvement = real'(baseline_transactions - ai_transactions) / real'(baseline_transactions) * 100.0;
        `uvm_info(get_type_name(), $sformatf(
            "  Transaction Reduction: %.1f%%", txn_improvement), UVM_MEDIUM)
    end
    
    if (baseline_time > 0) begin
        time_improvement = (baseline_time - ai_time) / baseline_time * 100.0;
        `uvm_info(get_type_name(), $sformatf(
            "  Time Reduction: %.1f%%", time_improvement), UVM_MEDIUM)
    end
    
    coverage_delta = ai_coverage - baseline_coverage;
    `uvm_info(get_type_name(), $sformatf(
        "  Coverage Delta: %+.0f%%", coverage_delta*100), UVM_MEDIUM)
    
    // Print RL-specific reports if available
    if (env.alu_cvcl != null) begin
        `uvm_info(get_type_name(), "", UVM_MEDIUM)
        `uvm_info(get_type_name(), env.alu_cvcl.get_rl_coverage_report(), UVM_MEDIUM)
    end
    
    if (env.alu_scb != null) begin
        `uvm_info(get_type_name(), "", UVM_MEDIUM)
        `uvm_info(get_type_name(), env.alu_scb.get_rl_scoreboard_report(), UVM_MEDIUM)
    end
    
    `uvm_info(get_type_name(), "=", "=", 70)
endfunction

endclass : ALU_RL_Test

// Comparison result class
class comparison_result extends uvm_object;
    `uvm_object_utils(comparison_result)
    
    string baseline_algorithm;
    string ai_algorithm;
    
    integer baseline_transactions;
    integer ai_transactions;
    
    real baseline_coverage;
    real ai_coverage;
    
    time baseline_time;
    time ai_time;
    
    real transaction_reduction;
    real time_reduction;
    real coverage_delta;
    
    function new(string name = "comparison_result");
        super.new(name);
    endfunction
    
    function void calculate_improvements();
        if (baseline_transactions > 0) begin
            transaction_reduction = real'(baseline_transactions - ai_transactions) / 
                                   real'(baseline_transactions) * 100.0;
        end
        
        if (baseline_time > 0) begin
            time_reduction = real'(baseline_time - ai_time) / real'(baseline_time) * 100.0;
        end
        
        coverage_delta = ai_coverage - baseline_coverage;
    endfunction
    
    function string convert2string();
        string s;
        s = $sformatf("Comparison Result:\n");
        s = {s, $sformatf("  Baseline: %s, %0d txn, %.0f%% cov\n", 
              baseline_algorithm, baseline_transactions, baseline_coverage*100)};
        s = {s, $sformatf("  AI: %s, %0d txn, %.0f%% cov\n", 
              ai_algorithm, ai_transactions, ai_coverage*100)};
        s = {s, $sformatf("  Improvements:\n")};
        s = {s, $sformatf("    Transactions: %.1f%%\n", transaction_reduction)};
        s = {s, $sformatf("    Time: %.1f%%\n", time_reduction)};
        s = {s, $sformatf("    Coverage: %+.0f%%\n", coverage_delta*100)};
        return s;
    endfunction
endclass