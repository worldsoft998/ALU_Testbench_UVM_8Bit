// =============================================================================
// PyHDL-IF Bridge: SystemVerilog Side
// =============================================================================
// Reads stimulus from Python RL agent via named pipe (FIFO) or file,
// and writes responses (results + coverage) back.
//
// Communication Protocol:
//   Python -> SV (stimulus pipe):
//     STIMULUS <seq_id> <A> <B> <op_code> <C_in> <reset> <timestamp>
//     DONE 0 0 0 0 0 0 <timestamp>
//
//   SV -> Python (response pipe):
//     RESPONSE <seq_id> <result> <C_out> <Z_flag> <cov_pct> <bins_hit> <bins_total> <errors> <timestamp>
//     DONE 0 0 0 0 0.0 0 0 0 <timestamp>
//
// No DPI-C or C-based intermediary is used.
// =============================================================================

class pyhdl_if_bridge;

    // File descriptors
    int stim_fd;
    int resp_fd;
    int cov_fd;

    // Paths
    string stim_file_path;
    string resp_file_path;
    string cov_file_path;

    // State
    bit is_connected;
    bit is_file_mode;
    bit is_done;
    int transaction_count;
    int error_count;

    // Current stimulus
    int unsigned seq_id;
    logic [7:0]  stim_A;
    logic [7:0]  stim_B;
    logic [3:0]  stim_op_code;
    bit          stim_C_in;
    bit          stim_reset;

    // Timeout configuration
    int timeout_cycles;

    // Constructor
    function new(string stim_path = "", string resp_path = "", string cov_path = "");
        if (stim_path == "") begin
            // Default: named pipe mode
            stim_file_path = "/tmp/alu_rl_bridge/py2sv_stimulus.pipe";
            resp_file_path = "/tmp/alu_rl_bridge/sv2py_response.pipe";
            cov_file_path  = "/tmp/alu_rl_bridge/coverage_report.txt";
            is_file_mode = 0;
        end else begin
            // File mode
            stim_file_path = stim_path;
            resp_file_path = resp_path;
            cov_file_path  = cov_path;
            is_file_mode = 1;
        end

        is_connected = 0;
        is_done = 0;
        transaction_count = 0;
        error_count = 0;
        timeout_cycles = 100000;

        `uvm_info("BRIDGE", $sformatf("PyHDL-IF Bridge created: stim=%s, resp=%s",
            stim_file_path, resp_file_path), UVM_LOW)
    endfunction

    // Connect: open files/pipes
    function bit connect();
        stim_fd = $fopen(stim_file_path, "r");
        if (stim_fd == 0) begin
            `uvm_error("BRIDGE", $sformatf("Cannot open stimulus file: %s", stim_file_path))
            return 0;
        end

        resp_fd = $fopen(resp_file_path, "w");
        if (resp_fd == 0) begin
            `uvm_error("BRIDGE", $sformatf("Cannot open response file: %s", resp_file_path))
            $fclose(stim_fd);
            return 0;
        end

        is_connected = 1;
        `uvm_info("BRIDGE", "Bridge connected successfully", UVM_LOW)
        return 1;
    endfunction

    // Disconnect: close files/pipes
    function void disconnect();
        if (resp_fd != 0) begin
            // Send DONE message
            $fwrite(resp_fd, "DONE 0 0 0 0 0.0000 0 0 0 0.000000\n");
            $fflush(resp_fd);
            $fclose(resp_fd);
        end
        if (stim_fd != 0)
            $fclose(stim_fd);
        if (cov_fd != 0)
            $fclose(cov_fd);

        is_connected = 0;
        `uvm_info("BRIDGE", $sformatf("Bridge disconnected. Total transactions: %0d, Errors: %0d",
            transaction_count, error_count), UVM_LOW)
    endfunction

    // Read next stimulus from pipe/file
    // Returns 1 if stimulus read successfully, 0 if DONE or error
    function bit read_stimulus();
        string msg_type;
        int unsigned sid;
        int a_val, b_val, op_val, cin_val, rst_val;
        real ts;
        int scan_result;
        string line;

        if (!is_connected || is_done) return 0;

        // Read a line and parse
        scan_result = $fscanf(stim_fd, "%s %d %d %d %d %d %d %f\n",
            msg_type, sid, a_val, b_val, op_val, cin_val, rst_val, ts);

        if (scan_result < 7) begin
            // Check for comments or empty lines
            if (scan_result == 0 || scan_result == -1) begin
                is_done = 1;
                return 0;
            end
            `uvm_warning("BRIDGE", $sformatf("Incomplete stimulus read, got %0d fields", scan_result))
            return 0;
        end

        // Check for DONE signal
        if (msg_type == "DONE" || msg_type == "#") begin
            is_done = 1;
            `uvm_info("BRIDGE", "Received DONE from Python", UVM_LOW)
            return 0;
        end

        // Parse stimulus
        seq_id       = sid;
        stim_A       = a_val[7:0];
        stim_B       = b_val[7:0];
        stim_op_code = op_val[3:0];
        stim_C_in    = cin_val[0];
        stim_reset   = rst_val[0];

        transaction_count++;
        return 1;
    endfunction

    // Write response back to Python
    function void write_response(
        int unsigned sid,
        logic [15:0] result,
        bit c_out,
        bit z_flag,
        real coverage_pct,
        int coverage_bins_hit,
        int coverage_bins_total,
        int errors
    );
        if (!is_connected) return;

        $fwrite(resp_fd, "RESPONSE %0d %0d %0d %0d %0.4f %0d %0d %0d %0.6f\n",
            sid, result, c_out, z_flag,
            coverage_pct, coverage_bins_hit, coverage_bins_total,
            errors, $realtime / 1.0e9);
        $fflush(resp_fd);
    endfunction

    // Write coverage report to separate file
    function void write_coverage_report(
        real total_coverage,
        int corner_cases_hit,
        int cross_bins_hit,
        int total_transactions
    );
        cov_fd = $fopen(cov_file_path, "w");
        if (cov_fd == 0) begin
            `uvm_error("BRIDGE", $sformatf("Cannot open coverage file: %s", cov_file_path))
            return;
        end

        $fwrite(cov_fd, "# ALU Coverage Report\n");
        $fwrite(cov_fd, "total_coverage = %0.4f\n", total_coverage);
        $fwrite(cov_fd, "corner_cases_hit = %0d\n", corner_cases_hit);
        $fwrite(cov_fd, "cross_bins_hit = %0d\n", cross_bins_hit);
        $fwrite(cov_fd, "transactions_count = %0d\n", total_transactions);
        $fflush(cov_fd);
        $fclose(cov_fd);
        cov_fd = 0;

        `uvm_info("BRIDGE", $sformatf("Coverage report written: %.2f%%", total_coverage), UVM_LOW)
    endfunction

    // Check if more stimuli available
    function bit has_more();
        return is_connected && !is_done;
    endfunction

endclass : pyhdl_if_bridge
