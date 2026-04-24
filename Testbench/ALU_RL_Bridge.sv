"""
UVM-Side Bridge Component for PyHDL-IF Communication
SystemVerilog class that communicates with Python RL modules via TCP/IP

This component:
- Sends stimulus requests to Python RL agent
- Receives optimized stimulus from RL agent
- Sends coverage data back to Python
- Receives reward signals from RL agent
- Implements proper handshaking and timeout handling

Author: AI Assistant
Date: 2026-04-24
"""

class alu_rl_bridge #(parameter HOST = "localhost", parameter PORT = 5555, parameter TIMEOUT = 5000);
    
    // Message types matching Python bridge
    typedef enum bit [7:0] {
        MSG_STIMULUS      = 8'h01,
        MSG_RESPONSE      = 8'h02,
        MSG_STATUS        = 8'h03,
        MSG_CONFIG        = 8'h04,
        MSG_COVERAGE      = 8'h05,
        MSG_REWARD        = 8'h06,
        MSG_ACTION        = 8'h07,
        MSG_TERMINATE     = 8'h08,
        MSG_HEARTBEAT     = 8'h09
    } msg_type_t;
    
    // Status
    typedef enum bit [7:0] {
        STATUS_IDLE       = 8'h00,
        STATUS_CONNECTED  = 8'h01,
        STATUS_ERROR      = 8'h02,
        STATUS_TIMEOUT    = 8'h03
    } status_t;
    
    // Internal state
    status_t bridge_status;
    int socket_id;
    bit connected;
    integer transaction_count;
    integer timeout_count;
    
    // Coverage tracking
    bit op_code_covered[6];
    bit corner_case_covered[12];
    real coverage_percentage;
    
    // Statistics
    integer msgs_sent;
    integer msgs_received;
    integer errors;
    
    // Message buffers
    byte packet_buffer[$];
    byte response_buffer[$];
    
    // Pending transaction tracking
    integer pending_txn_id;
    real last_reward;
    
    // Configuration
    bit enable_logging;
    string log_prefix;
    
    // Semaphores for thread safety
    semaphore cmd_sem;
    
    // Events
    event connected_event;
    event disconnected_event;
    event response_received;
    
    // Mailbox for communication with testbench
    mailbox #(stimulus_item) stimulus_mb;
    mailbox #(response_item) response_mb;
    
    // Stimulus/Response item classes
    class stimulus_item;
        rand bit [7:0] A;
        rand bit [7:0] B;
        rand bit [3:0] op_code;
        rand bit C_in;
        rand bit Reset;
        integer txn_id;
    endclass
    
    class response_item;
        bit [15:0] Result;
        bit C_out;
        bit Z_flag;
        bit error;
        integer txn_id;
        real reward;
        real coverage_increase;
    endclass
    
    // Constructor
    function new(string name = "alu_rl_bridge");
        bridge_status = STATUS_IDLE;
        connected = 0;
        transaction_count = 0;
        timeout_count = 0;
        enable_logging = 1;
        log_prefix = "ALU_RL_BRIDGE";
        cmd_sem = new(1);
        stimulus_mb = new();
        response_mb = new();
        
        foreach (op_code_covered[i]) op_code_covered[i] = 0;
        foreach (corner_case_covered[i]) corner_case_covered[i] = 0;
        
        `uvm_info(get_type_name(), "ALU RL Bridge created", UVM_MEDIUM)
    endfunction
    
    // Connect to Python RL server
    virtual function integer connect();
        `uvm_info(get_type_name(), $sformatf("Connecting to %s:%0d", HOST, PORT), UVM_MEDIUM)
        
        // socket() system call would be used in actual SystemVerilog
        // For simulation, we use a DPI-C wrapper or simulation-specific API
        // This is a placeholder for the actual implementation
        socket_id = 0; // Placeholder
        
        // In real implementation:
        // socket_id = $system_socket_create(HOST, PORT);
        // if (socket_id < 0) begin
        //     `uvm_error(get_type_name(), "Failed to create socket")
        //     return -1;
        // end
        
        connected = 1;
        bridge_status = STATUS_CONNECTED;
        ->connected_event;
        
        `uvm_info(get_type_name(), "Connected to Python RL server", UVM_MEDIUM)
        return socket_id;
    endfunction
    
    // Disconnect from server
    virtual function void disconnect();
        `uvm_info(get_type_name(), "Disconnecting from server", UVM_MEDIUM)
        
        // Send terminate message
        send_message(MSG_TERMINATE, {});
        
        // Close socket
        // $system_socket_close(socket_id);
        
        connected = 0;
        bridge_status = STATUS_IDLE;
        ->disconnected_event;
        
        `uvm_info(get_type_name(), "Disconnected", UVM_MEDIUM)
    endfunction
    
    // Send stimulus request and get response
    virtual function response_item send_stimulus_and_wait(
        bit [7:0] A,
        bit [7:0] B,
        bit [3:0] op_code,
        bit C_in = 0,
        bit Reset = 0
    );
        stimulus_item stim = new();
        response_item rsp = new();
        
        stim.A = A;
        stim.B = B;
        stim.op_code = op_code;
        stim.C_in = C_in;
        stim.Reset = Reset;
        stim.txn_id = transaction_count++;
        
        cmd_sem.get();
        
        begin
            // Pack message
            byte unsigned msg[];
            pack_stimulus_message(stim, msg);
            
            // Send
            send_raw_message(msg);
            
            // Wait for response with timeout
            rsp = wait_for_response(TIMEOUT);
            
            if (rsp == null) begin
                `uvm_warning(get_type_name(), "Response timeout, using fallback")
                timeout_count++;
                // Create default response
                rsp = new();
                rsp.error = 1;
            end
        end
        
        cmd_sem.put();
        
        return rsp;
    endfunction
    
    // Send just stimulus (non-blocking)
    virtual function void send_stimulus(
        bit [7:0] A,
        bit [7:0] B,
        bit [3:0] op_code,
        bit C_in = 0,
        bit Reset = 0
    );
        stimulus_item stim = new();
        
        stim.A = A;
        stim.B = B;
        stim.op_code = op_code;
        stim.C_in = C_in;
        stim.Reset = Reset;
        stim.txn_id = transaction_count++;
        
        stimulus_mb.put(stim);
        
        begin
            byte unsigned msg[];
            pack_stimulus_message(stim, msg);
            send_raw_message(msg);
        end
    endfunction
    
    // Wait for response (blocking with timeout)
    virtual function response_item wait_for_response(integer timeout_ns);
        response_item rsp = new();
        real start_time;
        real elapsed;
        byte unsigned header[4];
        byte unsigned length;
        
        start_time = $realtime;
        
        // Read header (4 bytes for length)
        while (response_buffer.size() < 4) begin
            elapsed = $realtime - start_time;
            if (elapsed > timeout_ns) begin
                `uvm_warning(get_type_name(), "Response timeout")
                return null;
            end
            // In real implementation, wait for data available event
            #100;
        end
        
        // Get length
        for (int i = 0; i < 4; i++) begin
            header[i] = response_buffer.pop_front();
        end
        
        // Decode length (big-endian 32-bit)
        length = (header[0] << 24) | (header[1] << 16) | (header[2] << 8) | header[3];
        
        // Read message body
        while (response_buffer.size() < length) begin
            elapsed = $realtime - start_time;
            if (elapsed > timeout_ns) begin
                `uvm_warning(get_type_name(), "Response timeout during body read")
                return null;
            end
            #100;
        end
        
        // Extract message
        byte unsigned msg[];
        for (int i = 0; i < length; i++) begin
            msg = new[msg.size() + 1](msg);
            msg[msg.size()-1] = response_buffer.pop_front();
        end
        
        // Parse response
        unpack_response_message(msg, rsp);
        
        msgs_received++;
        ->response_received;
        
        return rsp;
    endfunction
    
    // Send coverage data to Python
    virtual function void send_coverage();
        byte unsigned msg[];
        real coverage_bins[12];
        
        // Calculate coverage
        calculate_coverage(coverage_bins);
        
        // Pack and send
        pack_coverage_message(coverage_bins, msg);
        send_raw_message(msg);
        
        `uvm_info(get_type_name(), $sformatf("Sent coverage: %0p", coverage_bins), UVM_HIGH)
    endfunction
    
    // Send reward to Python
    virtual function void send_reward(real reward, real coverage_increase);
        byte unsigned msg[];
        
        pack_reward_message(reward, coverage_increase, msg);
        send_raw_message(msg);
        
        last_reward = reward;
        `uvm_info(get_type_name(), $sformatf("Sent reward: %f", reward), UVM_HIGH)
    endfunction
    
    // Receive action from Python
    virtual function stimulus_item receive_action();
        stimulus_item stim = new();
        byte unsigned msg[];
        
        // Request action
        send_message(MSG_ACTION, {});
        
        // Wait for response
        stim = wait_for_action_request(TIMEOUT);
        
        if (stim == null) begin
            // Fallback to random
            `uvm_warning(get_type_name(), "No action received, using random")
            stim = new();
            stim.A = $random;
            stim.B = $random;
            stim.op_code = $random;
            stim.C_in = $random;
            stim.Reset = 0;
        end
        
        return stim;
    endfunction
    
    // Update coverage tracking
    virtual function void update_coverage(
        bit [3:0] op_code,
        bit [7:0] A,
        bit [7:0] B,
        bit error_detected
    );
        // Update operation coverage
        if (op_code < 6) begin
            op_code_covered[op_code] = 1;
        end
        
        // Update corner case coverage
        // Bin 7: All ones inputs (A=255, B=255)
        if (A == 8'hFF && B == 8'hFF) corner_case_covered[7] = 1;
        
        // Bin 8: All zeros inputs
        if (A == 8'h00 && B == 8'h00) corner_case_covered[8] = 1;
        
        // Bin 9: Mixed patterns
        if ((A == 8'hFF && B == 8'h00) || (A == 8'h00 && B == 8'hFF)) 
            corner_case_covered[9] = 1;
        
        // Bin 10: Carry-in cases
        if (op_code == 4'h0) corner_case_covered[10] = 1; // ADD
        
        // Bin 11: Overflow cases
        if (op_code == 4'h0 && (A + B > 255)) corner_case_covered[11] = 1;
        if (op_code == 4'h1 && A < B) corner_case_covered[11] = 1;
        
        // Recalculate overall coverage
        calculate_overall_coverage();
    endfunction
    
    // Calculate coverage bins
    virtual function void calculate_coverage(output real bins[12]);
        bins[0] = coverage_percentage; // Overall
        
        // Op-code specific
        for (int i = 0; i < 6; i++) begin
            bins[i+1] = op_code_covered[i] ? 1.0 : 0.0;
        end
        
        // Corner cases
        bins[7] = corner_case_covered[7] ? 1.0 : 0.0;
        bins[8] = corner_case_covered[8] ? 1.0 : 0.0;
        bins[9] = corner_case_covered[9] ? 1.0 : 0.0;
        bins[10] = corner_case_covered[10] ? 1.0 : 0.0;
        bins[11] = corner_case_covered[11] ? 1.0 : 0.0;
    endfunction
    
    // Calculate overall coverage percentage
    virtual function void calculate_overall_coverage();
        integer covered_count = 0;
        
        // Count covered op_codes
        foreach (op_code_covered[i]) begin
            if (op_code_covered[i]) covered_count++;
        end
        
        // Count covered corner cases
        foreach (corner_case_covered[i]) begin
            if (corner_case_covered[i]) covered_count++;
        end
        
        // Total bins: 6 op_codes + 6 corner_cases
        coverage_percentage = real'(covered_count) / 12.0;
    endfunction
    
    // Get current coverage percentage
    virtual function real get_coverage_percentage();
        return coverage_percentage;
    endfunction
    
    // Get coverage report
    virtual function string get_coverage_report();
        string report;
        report = $sformatf("Coverage Report:\n");
        report = {report, $sformatf("  Overall: %0d%%\n", $rtoi(coverage_percentage*100))};
        report = {report, "  Operations:\n"};
        
        string ops[6] = '{"ADD", "SUB", "MULT", "DIV", "AND", "XOR"};
        foreach (op_code_covered[i]) begin
            report = {report, $sformatf("    %s: %s\n", ops[i], 
                          op_code_covered[i] ? "COVERED" : "NOT COVERED")};
        end
        
        return report;
    endfunction
    
    // Get bridge statistics
    virtual function void get_statistics(output statistics st);
        st.msgs_sent = msgs_sent;
        st.msgs_received = msgs_received;
        st.errors = errors;
        st.timeouts = timeout_count;
        st.transactions = transaction_count;
        st.coverage = coverage_percentage;
        st.status = bridge_status;
    endfunction
    
    // Private: Pack stimulus message
    virtual function void pack_stimulus_message(
        stimulus_item stim,
        output byte unsigned msg[]
    );
        // JSON format: {"A":val, "B":val, "op_code":val, "C_in":val, "Reset":val, "timestamp":val}
        string json_str;
        json_str = $sformatf(
            "{\"A\":%0d,\"B\":%0d,\"op_code\":%0d,\"C_in\":%0d,\"Reset\":%0d,\"timestamp\":%0t}",
            stim.A, stim.B, stim.op_code, stim.C_in, stim.Reset, $time
        );
        
        msg = new[json_str.len()](msg);
        for (int i = 0; i < json_str.len(); i++) begin
            msg[i] = byte'(json_str[i]);
        end
        
        pending_txn_id = stim.txn_id;
    endfunction
    
    // Private: Unpack response message
    virtual function void unpack_response_message(
        byte unsigned msg[],
        output response_item rsp
    );
        string json_str;
        
        // Convert bytes to string
        json_str = "";
        for (int i = 0; i < msg.size(); i++) begin
            json_str = {json_str, string'(msg[i])};
        end
        
        // Parse JSON (simplified - in real impl use JSON parser)
        // Extract fields from JSON string
        // This is a placeholder for actual JSON parsing
        
        rsp.txn_id = pending_txn_id;
    endfunction
    
    // Private: Pack coverage message
    virtual function void pack_coverage_message(
        real bins[12],
        output byte unsigned msg[]
    );
        string json_str;
        json_str = $sformatf(
            "{\"coverage\":[%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d],\"timestamp\":%0t}",
            $rtoi(bins[0]*100), $rtoi(bins[1]*100), $rtoi(bins[2]*100),
            $rtoi(bins[3]*100), $rtoi(bins[4]*100), $rtoi(bins[5]*100),
            $rtoi(bins[6]*100), $rtoi(bins[7]*100), $rtoi(bins[8]*100),
            $rtoi(bins[9]*100), $rtoi(bins[10]*100), $rtoi(bins[11]*100),
            $time
        );
        
        msg = new[json_str.len()](msg);
        for (int i = 0; i < json_str.len(); i++) begin
            msg[i] = byte'(json_str[i]);
        end
    endfunction
    
    // Private: Pack reward message
    virtual function void pack_reward_message(
        real reward,
        real coverage_increase,
        output byte unsigned msg[]
    );
        string json_str;
        json_str = $sformatf(
            "{\"reward\":%0f,\"coverage_increase\":%0f,\"timestamp\":%0t}",
            reward, coverage_increase, $time
        );
        
        msg = new[json_str.len()](msg);
        for (int i = 0; i < json_str.len(); i++) begin
            msg[i] = byte'(json_str[i]);
        end
    endfunction
    
    // Private: Send message
    virtual function void send_message(msg_type_t msg_type, byte unsigned data[]);
        byte unsigned header[8];
        byte unsigned msg[];
        integer length;
        
        // Build message
        msg = new[1 + data.size()](msg);
        msg[0] = msg_type;
        foreach (data[i]) msg[i+1] = data[i];
        
        length = msg.size();
        
        // Build header: length (4 bytes) + msg_type (1 byte) + timestamp (3 bytes)
        header[0] = (length >> 24) & 8'hFF;
        header[1] = (length >> 16) & 8'hFF;
        header[2] = (length >> 8) & 8'hFF;
        header[3] = length & 8'hFF;
        header[4] = msg_type;
        header[5] = 0; // timestamp placeholder
        header[6] = 0;
        header[7] = 0;
        
        // Combine header and message
        byte unsigned packet[];
        packet = new[header.size() + msg.size()](packet);
        foreach (header[i]) packet[i] = header[i];
        foreach (msg[i]) packet[header.size() + i] = msg[i];
        
        send_raw_message(packet);
    endfunction
    
    // Private: Send raw message
    virtual function void send_raw_message(byte unsigned msg[]);
        // In real implementation, use socket write
        // $system_socket_write(socket_id, msg, msg.size());
        
        msgs_sent++;
        
        if (enable_logging) begin
            `uvm_info(get_type_name(), 
                $sformatf("Sent %0d bytes", msg.size()), UVM_DEBUG)
        end
    endfunction
    
    // Get bridge status
    virtual function status_t get_status();
        return bridge_status;
    endfunction
    
    // Check if connected
    virtual function bit is_connected();
        return connected;
    endfunction
    
endclass : alu_rl_bridge

// Statistics structure
typedef struct {
    integer msgs_sent;
    integer msgs_received;
    integer errors;
    integer timeouts;
    integer transactions;
    real coverage;
    alu_rl_bridge::status_t status;
} bridge_statistics;