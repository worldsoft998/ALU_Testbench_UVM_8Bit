class alu_rl_sequence extends uvm_sequence #(ALU_Sequence_Item);
    `uvm_object_utils(alu_rl_sequence)

    // Configuration
    bit use_ai_generation;
    alu_rl_bridge bridge;
    integer num_transactions;
    real target_coverage;
    
    // Coverage tracking
    real current_coverage;
    real last_reward;
    integer transactions_completed;
    
    // Statistics
    integer ai_transactions;
    integer random_transactions;
    real coverage_increase;
    
    // State
    typedef enum {IDLE, WAITING_RESPONSE, PROCESSING} state_t;
    state_t current_state;
    
    // Mailbox for receiving AI-generated stimuli
    mailbox #(ALU_Sequence_Item) ai_stimulus_mb;
    
    function new(string name = "alu_rl_sequence");
        super.new(name);
        use_ai_generation = 0;
        num_transactions = 10000;
        target_coverage = 0.95;
        current_coverage = 0.0;
        last_reward = 0.0;
        transactions_completed = 0;
        ai_transactions = 0;
        random_transactions = 0;
        current_state = IDLE;
        ai_stimulus_mb = new();
    endfunction

    task body();
        ALU_Sequence_Item item;
        ALU_Sequence_Item ai_item;
        bit use_ai;
        
        `uvm_info(get_type_name(), $sformatf("Starting RL sequence: %0d transactions, AI=%0d", 
            num_transactions, use_ai_generation), UVM_MEDIUM)
        
        // Apply reset first
        item = ALU_Sequence_Item::type_id::create("reset_item");
        start_item(item);
        if (!item.randomize() with {Reset == 1'b1;}) begin
            `uvm_error(get_type_name(), "Failed to randomize reset item")
        end
        finish_item(item);
        
        #100;
        
        // Main transaction loop
        for (int i = 0; i < num_transactions; i++) begin
            item = ALU_Sequence_Item::type_id::create($sformatf("item_%0d", i));
            
            // Determine whether to use AI-generated stimulus
            use_ai = use_ai_generation && (i % 10 == 0); // Use AI every 10th transaction
            
            if (use_ai) begin
                // Get AI-generated stimulus from bridge
                if (bridge != null && bridge.is_connected()) begin
                    // Get from bridge (blocking call)
                    get_ai_stimulus_from_bridge(item);
                    ai_transactions++;
                end else begin
                    // Fallback to random if bridge not available
                    generate_random_stimulus(item);
                    random_transactions++;
                end
            end else begin
                // Use random generation
                generate_intelligent_random_stimulus(item);
                random_transactions++;
            end
            
            // Send stimulus
            start_item(item);
            finish_item(item);
            
            transactions_completed++;
            
            // Update coverage
            if (bridge != null) begin
                bridge.update_coverage(
                    item.op_code,
                    item.A,
                    item.B,
                    0  // No error detected yet
                );
                
                current_coverage = bridge.get_coverage_percentage();
                
                // Send coverage and get reward
                bridge.send_coverage();
                
                // Calculate reward
                last_reward = calculate_reward(
                    current_coverage - coverage_increase,
                    current_coverage,
                    item.op_code,
                    item.A,
                    item.B
                );
                
                // Send reward
                bridge.send_reward(last_reward, current_coverage - coverage_increase);
                
                coverage_increase = current_coverage;
                
                // Check if coverage target reached
                if (current_coverage >= target_coverage) begin
                    `uvm_info(get_type_name(), $sformatf(
                        "Target coverage %0d%% reached at transaction %0d", 
                        $rtoi(target_coverage*100), i), UVM_MEDIUM)
                    break;
                end
            end
            
            #20; // Small delay between transactions
            
            // Progress reporting
            if (i % 1000 == 0) begin
                `uvm_info(get_type_name(), $sformatf(
                    "Progress: %0d/%0d transactions, Coverage: %0d%%, AI used: %0d/%0d",
                    i, num_transactions, $rtoi(current_coverage*100),
                    ai_transactions, transactions_completed), UVM_MEDIUM)
            end
        end
        
        `uvm_info(get_type_name(), $sformatf(
            "Sequence completed: %0d transactions, Coverage: %0d%%, AI: %0d, Random: %0d",
            transactions_completed, $rtoi(current_coverage*100),
            ai_transactions, random_transactions), UVM_MEDIUM)
    endtask
    
    // Get AI-generated stimulus from bridge
    virtual task get_ai_stimulus_from_bridge(output ALU_Sequence_Item item);
        stimulus_item stim;
        
        current_state = WAITING_RESPONSE;
        
        // Request action from Python RL agent
        stim = bridge.receive_action();
        
        current_state = PROCESSING;
        
        // Convert bridge stimulus to sequence item
        item.A = stim.A;
        item.B = stim.B;
        item.op_code = stim.op_code;
        item.C_in = stim.C_in;
        item.Reset = 0;
        
        `uvm_info(get_type_name(), $sformatf(
            "AI-generated stimulus: A=%0d, B=%0d, op=%0d", 
            item.A, item.B, item.op_code), UVM_HIGH)
    endtask
    
    // Generate random stimulus (baseline)
    virtual function void generate_random_stimulus(output ALU_Sequence_Item item);
        if (!item.randomize() with {Reset == 0;}) begin
            `uvm_error(get_type_name(), "Failed to randomize item")
        end
    endfunction
    
    // Generate intelligent random stimulus with some bias
    virtual function void generate_intelligent_random_stimulus(output ALU_Sequence_Item item);
        bit [3:0] target_op;
        bit [7:0] target_a, target_b;
        
        // 20% chance of targeting uncovered operations
        if ($urandom() % 100 < 20) begin
            // Find least-covered operation
            target_op = find_least_covered_op();
        end else begin
            target_op = $urandom() % 6;
        end
        
        // 10% chance of corner case values
        if ($urandom() % 100 < 10) begin
            target_a = $urandom() % 2 ? 8'hFF : 8'h00;
            target_b = $urandom() % 2 ? 8'hFF : 8'h00;
        end else begin
            target_a = $urandom() % 256;
            target_b = $urandom() % 256;
        end
        
        if (!item.randomize() with {
            Reset == 0;
            op_code == target_op;
            A == target_a;
            B == target_b;
        }) begin
            // Fallback to fully random
            if (!item.randomize() with {Reset == 0;}) begin
                `uvm_error(get_type_name(), "Failed to randomize item")
            end
        end
    endfunction
    
    // Find least-covered operation code
    virtual function bit [3:0] find_least_covered_op();
        integer min_count = integer'(~0);
        bit [3:0] target_op = 0;
        
        // Access coverage collector
        alu_coverage_item cov_item;
        
        // This would be connected during build phase
        // For now, return random operation
        return $urandom() % 6;
    endfunction
    
    // Calculate reward based on coverage improvement
    virtual function real calculate_reward(
        real prev_coverage,
        real curr_coverage,
        bit [3:0] op_code,
        bit [7:0] A,
        bit [7:0] B
    );
        real reward = 0.0;
        real coverage_delta;
        
        coverage_delta = curr_coverage - prev_coverage;
        
        // Base reward for coverage increase
        reward += coverage_delta * 100.0;
        
        // Exploration bonus
        if (is_new_stimulus(op_code, A, B)) begin
            reward += 0.1;
        end
        
        // Corner case discovery bonus
        if ((A == 8'hFF && B == 8'hFF) || (A == 8'h00 && B == 8'h00)) begin
            reward += 0.5;
        end
        
        // Time penalty for efficiency
        reward -= 0.01;
        
        return reward;
    endfunction
    
    // Check if this is a new stimulus combination
    virtual function bit is_new_stimulus(bit [3:0] op_code, bit [7:0] A, bit [7:0] B);
        // Simple check - in real implementation, track seen combinations
        static bit seen[6][256][256];
        
        if (seen[op_code][A][B]) begin
            return 0;
        end else begin
            seen[op_code][A][B] = 1;
            return 1;
        end
    endfunction
    
    // Set configuration
    virtual function void set_config(
        bit use_ai,
        integer num_txn,
        real coverage_target
    );
        use_ai_generation = use_ai;
        num_transactions = num_txn;
        target_coverage = coverage_target;
        
        `uvm_info(get_type_name(), $sformatf(
            "Config set: AI=%0d, TXN=%0d, Coverage=%.0f%%",
            use_ai, num_txn, coverage_target*100), UVM_MEDIUM)
    endfunction
    
    // Get statistics
    virtual function void get_statistics(output rl_sequence_stats stats);
        stats.transactions_completed = transactions_completed;
        stats.ai_transactions = ai_transactions;
        stats.random_transactions = random_transactions;
        stats.final_coverage = current_coverage;
        stats.total_reward = last_reward;
    endfunction

endclass : alu_rl_sequence

// Statistics structure
typedef struct {
    integer transactions_completed;
    integer ai_transactions;
    integer random_transactions;
    real final_coverage;
    real total_reward;
} rl_sequence_stats;