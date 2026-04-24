class ALU_RL_Scoreboard extends ALU_Scoreboard;
`uvm_component_utils(ALU_RL_Scoreboard)

// RL-specific tracking
bit rl_enabled;
integer ai_generated_errors;
integer random_generated_errors;

// Error categorization
integer error_by_op[6];
integer error_by_range[4]; // low-low, low-high, high-low, high-high

// Performance metrics
real ai_error_detection_rate;
real random_error_detection_rate;
integer false_positives;
integer false_negatives;

// Bug tracking
bit bug_detected;
integer bug_count;
bit reported_bugs[$];

// Analysis
real error_rate_history[$];
integer transaction_at_error[$];

function new(string name = "ALU_RL_Scoreboard", uvm_component parent = null);
    super.new(name, parent);
    rl_enabled = 0;
    ai_generated_errors = 0;
    random_generated_errors = 0;
    bug_detected = 0;
    bug_count = 0;
    false_positives = 0;
    false_negatives = 0;
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    
    // Get RL configuration
    if (!uvm_config_db #(bit)::get(this, "", "rl_enabled", rl_enabled)) begin
        rl_enabled = 0;
    end
    
    `uvm_info(get_type_name(), $sformatf("RL Scoreboard built: RL=%0d", rl_enabled), UVM_MEDIUM)
endfunction

// Override compare for RL-aware error tracking
function void compare(ALU_Sequence_Item item);
   logic[15:0] Result;
   bit         C_out, Z_flag;
   bit         error_detected;
   bit         is_ai_generated;
   string      error_msg;

   // Determine if this was AI-generated (simplified check)
   is_ai_generated = is_ai_transaction(item);
   
   // Calculate expected result (same as parent)
   case (item.op_code)
    4'h0: begin // ADD
        Result = item.A + item.B + item.C_in;
        C_out = Result[8];
    end
    4'h1: begin // SUB
        Result = item.A - item.B;
        C_out = Result[8];
    end
    4'h2: begin // MULT
        Result = item.A * item.B;
        C_out = 0;
    end
    4'h3: begin // DIV
        if (item.B != 0)
            Result = item.A / item.B;
        else
            Result = 16'hFFFF; // Error case for division by zero
        C_out = 0;
    end
    4'h4: begin // AND
        Result = item.A & item.B;
        C_out = 0;
    end
    4'h5: begin // XOR
        Result = item.A ^ item.B;
        C_out = 0;
    end
   endcase
   
   Z_flag = (Result == 0) ? 1'b1 : 1'b0;
   
   // Check for errors
   error_detected = 0;
   
   if (!((Z_flag == item.Z_flag) && (Result == item.Result) && (C_out == item.C_out)) && (item.Reset != 1)) begin
       error_detected = 1;
       error_msg = $sformatf(
           "Mismatch: reset=%b cout=%b expected=%b A=%0d B=%0d opcode=%0d Result=%0d expected=%0d",
           item.Reset, item.C_out, C_out, item.A, item.B, item.op_code, item.Result, Result
       );
       
       `uvm_error(get_type_name(), error_msg)
       
       // Track error for RL feedback
       if (rl_enabled) begin
           track_error(item, is_ai_generated);
       end
   end
   
   if (!error_detected) begin
       `uvm_info(get_type_name(), "Comparison passed", UVM_HIGH)
   end
   
   // Update statistics
   update_comparison_stats(error_detected, is_ai_generated, item.op_code);
endfunction

// Track error for RL learning
virtual function void track_error(ALU_Sequence_Item item, bit is_ai);
    // Update error counts
    if (is_ai) begin
        ai_generated_errors++;
    end else begin
        random_generated_errors++;
    end
    
    // Categorize error
    if (item.op_code < 6) begin
        error_by_op[item.op_code]++;
    end
    
    // Categorize by range
    categorize_by_range(item);
    
    // Track bug if new
    if (is_new_bug(item)) begin
        bug_count++;
        bug_detected = 1;
        reported_bugs.push_back(bug_count);
    end
endfunction

// Categorize error by input range
virtual function void categorize_by_range(ALU_Sequence_Item item);
    // Low-Low: Both inputs < 64
    if (item.A < 64 && item.B < 64)
        error_by_range[0]++;
    // Low-High: A < 64, B >= 192
    else if (item.A < 64 && item.B >= 192)
        error_by_range[1]++;
    // High-Low: A >= 192, B < 64
    else if (item.A >= 192 && item.B < 64)
        error_by_range[2]++;
    // High-High: Both inputs >= 192
    else if (item.A >= 192 && item.B >= 192)
        error_by_range[3]++;
endfunction

// Check if this is a new bug
virtual function bit is_new_bug(ALU_Sequence_Item item);
    integer bug_sig;
    bug_sig = (item.op_code << 16) | (item.A << 8) | item.B;
    
    foreach (reported_bugs[i]) begin
        if (reported_bugs[i] == bug_sig) begin
            return 0;
        end
    end
    
    return 1;
endfunction

// Check if transaction was AI-generated
virtual function bit is_ai_transaction(ALU_Sequence_Item item);
    // Simplified check - in real implementation would track source
    return 0; // Placeholder
endfunction

// Update comparison statistics
virtual function void update_comparison_stats(
    bit error_detected,
    bit is_ai,
    bit [3:0] op_code
);
    error_rate_history.push_back(error_detected ? 1.0 : 0.0);
    transaction_at_error.push_back(transaction_count);
    
    if (error_rate_history.size() > 1000) begin
        error_rate_history.pop_front();
        transaction_at_error.pop_front();
    end
endfunction

// Get RL-specific scoreboard report
virtual function string get_rl_scoreboard_report();
    string report;
    real total_errors;
    real ai_rate;
    real random_rate;
    
    report = {"\n", "=", "=", "=", "=", "RL Scoreboard Report", "=", "=", "=", "=", "\n"};
    
    total_errors = ai_generated_errors + random_generated_errors;
    if (total_errors > 0) begin
        ai_rate = real'(ai_generated_errors) / total_errors * 100.0;
        random_rate = real'(random_generated_errors) / total_errors * 100.0;
    end else begin
        ai_rate = 0.0;
        random_rate = 0.0;
    end
    
    report = {report, $sformatf("Total Errors: %0d\n", total_errors)};
    report = {report, $sformatf("AI-Generated Errors: %0d (%.1f%%)\n", ai_generated_errors, ai_rate)};
    report = {report, $sformatf("Random Errors: %0d (%.1f%%)\n", random_generated_errors, random_rate)};
    report = {report, $sformatf("Unique Bugs Found: %0d\n", bug_count)};
    report = {report, "\n"};
    
    report = {report, "Errors by Operation:\n"};
    for (int i = 0; i < 6; i++) begin
        string ops[6] = '{"ADD", "SUB", "MULT", "DIV", "AND", "XOR"};
        report = {report, $sformatf("  %s: %0d\n", ops[i], error_by_op[i])};
    end
    
    report = {report, "\nErrors by Input Range:\n"};
    report = {report, "  Low-Low: both inputs < 64\n"};
    report = {report, $sformatf("    Count: %0d\n", error_by_range[0])};
    report = {report, "  Low-High: A < 64, B >= 192\n"};
    report = {report, $sformatf("    Count: %0d\n", error_by_range[1])};
    report = {report, "  High-Low: A >= 192, B < 64\n"};
    report = {report, $sformatf("    Count: %0d\n", error_by_range[2])};
    report = {report, "  High-High: both inputs >= 192\n"};
    report = {report, $sformatf("    Count: %0d\n", error_by_range[3])};
    
    return report;
endfunction

// Export data for RL agent
virtual function void export_scoreboard_data(output scoreboard_export exp);
    real total_errors;
    
    total_errors = ai_generated_errors + random_generated_errors;
    
    exp.total_errors = total_errors;
    exp.ai_errors = ai_generated_errors;
    exp.random_errors = random_generated_errors;
    exp.bugs_found = bug_count;
    exp.error_rate = total_errors > 0 ? real'(total_errors) / real'(transaction_count) : 0.0;
endfunction

endclass : ALU_RL_Scoreboard

// Scoreboard export for RL
typedef struct {
    integer total_errors;
    integer ai_errors;
    integer random_errors;
    integer bugs_found;
    real error_rate;
} scoreboard_export;