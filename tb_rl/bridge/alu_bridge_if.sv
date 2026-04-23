// ============================================================================
// alu_bridge_if.sv - Thin UVM-side wrappers around the PyHDL-IF TLM FIFOs
// ============================================================================
// Two small SystemVerilog interfaces expose high-level get/put tasks and
// has_data/can_put polling functions so the bridge component can be written
// without reaching into the PyHDL-IF internals directly. Each wrapper owns
// one instance of the corresponding pyhdl-if fifo, bound to a shared clock.
//
// Note: the actual FIFO module names come from pyhdl-if's shared sources
//       (tlm_hvl2hdl_fifo / tlm_hdl2hvl_fifo) which are added to the VCS
//       compile-time file list by the Makefile.
// ============================================================================
`ifndef ALU_BRIDGE_IF_SV
`define ALU_BRIDGE_IF_SV

interface alu_req_if(input logic clk, input logic rst);
    logic          valid;
    logic          ready;
    logic [63:0]   dat;

    // Python-to-HDL FIFO. Python `put()`s requests; HDL pops them here.
    tlm_hvl2hdl_fifo #(.Twidth(64), .Tdepth(16)) u_hvl2hdl (
        .clock (clk),
        .reset (rst),
        .valid (valid),
        .ready (ready),
        .dat_o (dat)
    );

    // Local counter to model count-visibility without touching the internals.
    int unsigned pending_cnt;
    always_ff @(posedge clk or posedge rst) begin
        if (rst)              pending_cnt <= 0;
        else if (valid && ready) pending_cnt <= pending_cnt - 1;
    end
    // Increment when Python pushes is observed indirectly by (valid && !ready).
    always_ff @(posedge clk) if (!rst && valid && pending_cnt == 0) pending_cnt <= 1;

    function automatic bit has_data();
        return valid;
    endfunction

    task automatic get(output logic [63:0] d);
        ready <= 1'b1;
        @(posedge clk);
        while (!valid) @(posedge clk);
        d = dat;
        ready <= 1'b0;
    endtask

    initial ready = 1'b0;
endinterface

interface alu_rsp_if(input logic clk, input logic rst);
    logic          valid;
    logic          ready;
    logic [63:0]   dat;

    tlm_hdl2hvl_fifo #(.Twidth(64), .Tdepth(16)) u_hdl2hvl (
        .clock (clk),
        .reset (rst),
        .valid (valid),
        .ready (ready),
        .dat_i (dat)
    );

    function automatic bit can_put();
        // There is space when the FIFO's ready is high or no backpressure.
        return (u_hdl2hvl.count != 16);
    endfunction

    task automatic put(input logic [63:0] d);
        dat   <= d;
        valid <= 1'b1;
        @(posedge clk);
        while (!u_hdl2hvl.ready) @(posedge clk);
        valid <= 1'b0;
    endtask

    initial begin
        valid = 1'b0;
        dat   = '0;
    end
endinterface

`endif
