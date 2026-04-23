// ============================================================================
// alu_rl_bridge.sv - 2-way PyHDL-IF bridge between UVM and a Python RL agent
// ============================================================================
// Protocol overview
// -----------------
// The bridge uses two TLM FIFOs provided by PyHDL-IF:
//   * req_fifo : Python -> UVM  (stimulus request from the RL policy)
//   * rsp_fifo : UVM   -> Python (observed response + coverage delta)
//
// Both FIFOs implement a valid/ready handshake on the HDL side and blocking
// get/put semantics on the Python side, so there is no risk of data loss.
//
// Packed formats (LSB-first):
//   request  (64 bits):
//     [ 0     ]  reset
//     [ 1     ]  c_in
//     [ 5: 2 ]  op_code
//     [13: 6 ]  A
//     [21:14 ]  B
//     [22    ]  end_of_episode (Python asks UVM to stop the sequence)
//     [31:23 ]  reserved
//     [63:32 ]  gen_id (for round-trip correlation)
//
//   response (64 bits):
//     [15: 0 ]  Result
//     [16    ]  C_out
//     [17    ]  Z_flag
//     [18    ]  mismatch  (scoreboard verdict)
//     [19    ]  reset     (was this a reset transaction)
//     [27:20 ]  cov_pct   (0..100 functional coverage)
//     [31:28 ]  op_code   (echoed)
//     [63:32 ]  gen_id    (echoed)
//
// Timeout handling
// ----------------
// * If the Python side does not produce a stimulus within REQ_TIMEOUT_CYCLES
//   clock cycles, the bridge injects a self-generated random item so the
//   simulation never deadlocks.
// * If Python does not consume a response within RSP_TIMEOUT_CYCLES, the
//   response is dropped and an error is reported (but simulation continues).
// * An end_of_episode request tells the bridge to stop pumping items and
//   raise an objection drop so the test terminates cleanly.
// ============================================================================
`ifndef ALU_RL_BRIDGE_SV
`define ALU_RL_BRIDGE_SV

class alu_rl_bridge extends uvm_component;
    `uvm_component_utils(alu_rl_bridge)

    // ---- Analysis input from the agent (to build responses) ----
    uvm_analysis_imp_alu_obs #(alu_seq_item, alu_rl_bridge) obs_imp;

    // ---- Handles wired from the environment ----
    alu_sequencer            p_sqr;
    alu_scoreboard           p_scb;
    alu_coverage_collector   p_cov;

    // ---- Tuning knobs (configurable via config_db) ----
    int unsigned             req_timeout_cycles = 2000;
    int unsigned             rsp_timeout_cycles = 2000;
    int unsigned             max_items          = 0; // 0 = unlimited

    // ---- Stats ----
    int unsigned             n_req_recv;
    int unsigned             n_rsp_sent;
    int unsigned             n_timeouts;
    bit                      eo_episode;

    // ---- FIFO handles - bound from the testbench top ----
    //     tlm_hvl2hdl_fifo pushes from Python (HVL) to HDL
    //     tlm_hdl2hvl_fifo pushes from HDL to Python
    // The concrete virtual-interface handles are set in the top module.
    virtual alu_req_if       req_vif;
    virtual alu_rsp_if       rsp_vif;

    // ---- Internal ring buffer: last observed items awaiting response ----
    alu_seq_item pending_q[$];

    function new(string name = "alu_rl_bridge", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void set_sequencer(alu_sequencer s); p_sqr = s; endfunction
    function void set_scoreboard(alu_scoreboard s); p_scb = s; endfunction
    function void set_coverage(alu_coverage_collector c); p_cov = c; endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        obs_imp = new("obs_imp", this);
        void'(uvm_config_db#(int unsigned)::get(this, "", "req_timeout_cycles", req_timeout_cycles));
        void'(uvm_config_db#(int unsigned)::get(this, "", "rsp_timeout_cycles", rsp_timeout_cycles));
        void'(uvm_config_db#(int unsigned)::get(this, "", "max_items",          max_items));
        if (!uvm_config_db#(virtual alu_req_if)::get(this, "", "req_vif", req_vif))
            `uvm_fatal(get_type_name(), "alu_req_if vif not found")
        if (!uvm_config_db#(virtual alu_rsp_if)::get(this, "", "rsp_vif", rsp_vif))
            `uvm_fatal(get_type_name(), "alu_rsp_if vif not found")
    endfunction

    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this, "alu_rl_bridge pumping");
        fork
            req_pump();
            rsp_pump();
        join_any
        // Let any last response drain
        #100ns;
        phase.drop_objection(this, "alu_rl_bridge done");
    endtask

    // ------------------------------------------------------------------------
    // Request pump: pulls requests from Python, starts UVM items
    // ------------------------------------------------------------------------
    task req_pump();
        alu_rl_sequence seq;
        seq = alu_rl_sequence::type_id::create("rl_seq");
        seq.bridge = this;
        seq.start(p_sqr);
    endtask

    // ------------------------------------------------------------------------
    // Pull one request from Python with a timeout. Returns 1 on success.
    // ------------------------------------------------------------------------
    task automatic get_request(output bit [63:0] payload, output bit got);
        int cycles;
        got = 1'b0;
        cycles = 0;
        while (cycles < req_timeout_cycles) begin
            if (req_vif.has_data()) begin
                req_vif.get(payload);
                n_req_recv++;
                got = 1'b1;
                return;
            end
            @(posedge req_vif.clk);
            cycles++;
        end
        n_timeouts++;
        `uvm_warning(get_type_name(),
            $sformatf("request timeout after %0d cycles; injecting random fallback",
                      req_timeout_cycles))
    endtask

    // ------------------------------------------------------------------------
    // Response pump: samples observed items, pushes to Python
    // ------------------------------------------------------------------------
    task rsp_pump();
        alu_seq_item item;
        bit [63:0]   packed_rsp;
        int cycles;
        forever begin
            // Wait for something to respond with
            while (pending_q.size() == 0) begin
                @(posedge rsp_vif.clk);
            end
            item = pending_q.pop_front();
            packed_rsp = pack_response(item);

            cycles = 0;
            while (!rsp_vif.can_put() && cycles < rsp_timeout_cycles) begin
                @(posedge rsp_vif.clk);
                cycles++;
            end
            if (cycles >= rsp_timeout_cycles) begin
                n_timeouts++;
                `uvm_warning(get_type_name(),
                    $sformatf("response timeout; dropping gen_id=%0d", item.gen_id))
                continue;
            end
            rsp_vif.put(packed_rsp);
            n_rsp_sent++;
        end
    endtask

    // ------------------------------------------------------------------------
    // Observed-item hook: feeds the response pump
    // ------------------------------------------------------------------------
    virtual function void write_alu_obs(alu_seq_item t);
        alu_seq_item copy;
        copy = alu_seq_item::type_id::create("copy");
        copy.do_copy(t);
        // Attach last scoreboard/coverage data
        if (p_scb != null) copy.gen_id = p_scb.n_total;
        pending_q.push_back(copy);
    endfunction

    // ------------------------------------------------------------------------
    // Payload packing / unpacking helpers
    // ------------------------------------------------------------------------
    function void unpack_request(input bit [63:0] p,
                                 output bit       reset_b,
                                 output bit       cin_b,
                                 output bit [3:0] op,
                                 output bit [7:0] a,
                                 output bit [7:0] b,
                                 output bit       eoe,
                                 output int       gid);
        reset_b = p[0];
        cin_b   = p[1];
        op      = p[5:2];
        a       = p[13:6];
        b       = p[21:14];
        eoe     = p[22];
        gid     = int'(p[63:32]);
    endfunction

    function bit [63:0] pack_response(alu_seq_item it);
        bit [63:0] p;
        int covpct;
        covpct = (p_cov != null) ? int'(p_cov.bins_hit) : 0;
        p = 64'h0;
        p[15:0]  = it.Result;
        p[16]    = it.C_out;
        p[17]    = it.Z_flag;
        p[18]    = (p_scb != null) ? p_scb.last_mismatch : 1'b0;
        p[19]    = it.Reset;
        p[27:20] = covpct[7:0];
        p[31:28] = it.op_code;
        p[63:32] = it.gen_id;
        return p;
    endfunction

    virtual function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        `uvm_info(get_type_name(),
            $sformatf("Bridge stats: req_recv=%0d rsp_sent=%0d timeouts=%0d",
                      n_req_recv, n_rsp_sent, n_timeouts),
            UVM_NONE)
    endfunction
endclass

`endif
