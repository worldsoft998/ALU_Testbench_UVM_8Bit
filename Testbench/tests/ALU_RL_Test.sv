// =============================================================================
// RL-Guided Test
// =============================================================================
// Test that uses RL-generated stimuli via the PyHDL-IF bridge.
// Supports both file-based and live-pipe modes.
//
// Plusargs:
//   +RL_STIM_FILE=<path>   : Path to RL stimulus file (file mode)
//   +RL_RESP_FILE=<path>   : Path for response output (file mode)
//   +RL_COV_FILE=<path>    : Path for coverage report
//   +RL_PIPE_DIR=<path>    : Named pipe directory (live mode)
//   +RL_MODE=file|live     : Bridge mode (default: file)
//   +RL_MAX_TX=<N>         : Max transactions (default: 1000)
// =============================================================================

class ALU_RL_Test extends uvm_test;
    `uvm_component_utils(ALU_RL_Test)

    ALU_Env env;
    pyhdl_if_bridge bridge;
    rst_sequence rst_seq;
    rl_batch_sequence rl_seq;

    // Configuration
    string rl_mode;
    string stim_file;
    string resp_file;
    string cov_file;
    string pipe_dir;
    int    max_transactions;

    function new(string name = "ALU_RL_Test", uvm_component parent = null);
        super.new(name, parent);
        `uvm_info(get_type_name(), "in ALU_RL_Test constructor", UVM_LOW)
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = ALU_Env::type_id::create("env", this);
        `uvm_info(get_type_name(), "in ALU_RL_Test build phase", UVM_LOW)

        // Parse plusargs for configuration
        if (!$value$plusargs("RL_MODE=%s", rl_mode))
            rl_mode = "file";

        if (!$value$plusargs("RL_STIM_FILE=%s", stim_file))
            stim_file = "sim_work/rl_stimuli.txt";

        if (!$value$plusargs("RL_RESP_FILE=%s", resp_file))
            resp_file = "sim_work/sv_responses.txt";

        if (!$value$plusargs("RL_COV_FILE=%s", cov_file))
            cov_file = "sim_work/coverage_report.txt";

        if (!$value$plusargs("RL_PIPE_DIR=%s", pipe_dir))
            pipe_dir = "/tmp/alu_rl_bridge";

        if (!$value$plusargs("RL_MAX_TX=%d", max_transactions))
            max_transactions = 1000;

        `uvm_info(get_type_name(), $sformatf(
            "RL Config: mode=%s, stim=%s, resp=%s, max_tx=%0d",
            rl_mode, stim_file, resp_file, max_transactions), UVM_LOW)
    endfunction : build_phase

    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        `uvm_info(get_type_name(), "in ALU_RL_Test connect phase", UVM_LOW)
    endfunction : connect_phase

    function void end_of_elaboration_phase(uvm_phase phase);
        super.end_of_elaboration_phase(phase);
        `uvm_info(get_type_name(), "in ALU_RL_Test end_of_elaboration_phase", UVM_LOW)
        this.print();
    endfunction : end_of_elaboration_phase

    task run_phase(uvm_phase phase);
        super.run_phase(phase);
        `uvm_info(get_type_name(), "in ALU_RL_Test run phase", UVM_LOW)

        phase.raise_objection(this);

        // ---- Reset sequence ----
        rst_seq = rst_sequence::type_id::create("rst_seq");
        rst_seq.start(env.alu_agt.alu_sequencer);

        // ---- Setup bridge ----
        if (rl_mode == "live") begin
            // Live mode: named pipes
            bridge = new(
                {pipe_dir, "/py2sv_stimulus.pipe"},
                {pipe_dir, "/sv2py_response.pipe"},
                cov_file
            );
        end else begin
            // File mode: regular files
            bridge = new(stim_file, resp_file, cov_file);
        end

        if (!bridge.connect()) begin
            `uvm_fatal(get_type_name(), "Failed to connect bridge")
        end

        // ---- Run RL batch sequence ----
        rl_seq = rl_batch_sequence::type_id::create("rl_seq");
        rl_seq.set_bridge(bridge);
        rl_seq.set_max_transactions(max_transactions);

        `uvm_info(get_type_name(), "Starting RL-guided sequence", UVM_LOW)
        rl_seq.start(env.alu_agt.alu_sequencer);

        // ---- Write coverage report ----
        begin
            real cov_pct;
            // Get functional coverage from the coverage collector
            cov_pct = $get_coverage();
            bridge.write_coverage_report(
                cov_pct,
                0,  // corner_cases_hit - extracted from covergroup if available
                0,  // cross_bins_hit
                bridge.transaction_count
            );
            `uvm_info(get_type_name(), $sformatf(
                "Final coverage: %.2f%%, Transactions: %0d",
                cov_pct, bridge.transaction_count), UVM_LOW)
        end

        // ---- Disconnect bridge ----
        bridge.disconnect();

        phase.drop_objection(this);
    endtask : run_phase

endclass : ALU_RL_Test


// =============================================================================
// Baseline Random Test (for comparison)
// =============================================================================
// Same as ALU_Test but with configurable transaction count via plusarg.
// Writes coverage report for comparison with RL test.
// =============================================================================

class ALU_Baseline_Test extends uvm_test;
    `uvm_component_utils(ALU_Baseline_Test)

    ALU_Env env;
    rst_sequence rst_seq;
    test_sequence tst_seq;

    int num_transactions;
    string cov_file;

    function new(string name = "ALU_Baseline_Test", uvm_component parent = null);
        super.new(name, parent);
        `uvm_info(get_type_name(), "in ALU_Baseline_Test constructor", UVM_LOW)
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = ALU_Env::type_id::create("env", this);

        if (!$value$plusargs("NUM_TX=%d", num_transactions))
            num_transactions = 80000;

        if (!$value$plusargs("COV_FILE=%s", cov_file))
            cov_file = "sim_work/baseline_coverage_report.txt";

        `uvm_info(get_type_name(), $sformatf(
            "Baseline Config: num_tx=%0d, cov_file=%s",
            num_transactions, cov_file), UVM_LOW)
    endfunction : build_phase

    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
    endfunction : connect_phase

    function void end_of_elaboration_phase(uvm_phase phase);
        super.end_of_elaboration_phase(phase);
        this.print();
        factory.print();
    endfunction : end_of_elaboration_phase

    task run_phase(uvm_phase phase);
        int cov_fd;
        real cov_pct;

        super.run_phase(phase);
        `uvm_info(get_type_name(), "in ALU_Baseline_Test run phase", UVM_LOW)

        phase.raise_objection(this);

        // Reset
        rst_seq = rst_sequence::type_id::create("rst_seq");
        rst_seq.start(env.alu_agt.alu_sequencer);

        // Run random transactions
        repeat(num_transactions) begin
            #20;
            tst_seq = test_sequence::type_id::create("tst_seq");
            tst_seq.start(env.alu_agt.alu_sequencer);
        end

        // Write coverage report
        cov_pct = $get_coverage();
        cov_fd = $fopen(cov_file, "w");
        if (cov_fd != 0) begin
            $fwrite(cov_fd, "# ALU Baseline Coverage Report\n");
            $fwrite(cov_fd, "total_coverage = %0.4f\n", cov_pct);
            $fwrite(cov_fd, "transactions_count = %0d\n", num_transactions);
            $fclose(cov_fd);
        end

        `uvm_info(get_type_name(), $sformatf(
            "Final coverage: %.2f%%, Transactions: %0d",
            cov_pct, num_transactions), UVM_LOW)

        phase.drop_objection(this);
    endtask : run_phase

endclass : ALU_Baseline_Test
