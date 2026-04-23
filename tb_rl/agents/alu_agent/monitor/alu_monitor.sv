// ============================================================================
// alu_monitor.sv - Observes stimulus and response, publishes on analysis port
// ============================================================================
// Samples stimulus on the posedge of CLK, then waits one more cycle for the
// DUT's registered outputs before broadcasting the completed transaction.
// ============================================================================
`ifndef ALU_MONITOR_SV
`define ALU_MONITOR_SV

class alu_monitor extends uvm_monitor;
    `uvm_component_utils(alu_monitor)

    virtual ALU_interface                          intf;
    uvm_analysis_port #(alu_seq_item)              mon_ap;

    function new(string name = "alu_monitor", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        mon_ap = new("mon_ap", this);
        if (!uvm_config_db#(virtual ALU_interface)::get(this, "", "intf", intf))
            `uvm_fatal(get_type_name(), "virtual ALU_interface not found")
    endfunction

    virtual task run_phase(uvm_phase phase);
        alu_seq_item s;
        forever begin
            s = alu_seq_item::type_id::create("s");
            @(posedge intf.CLK);
            s.Reset   = intf.Reset;
            s.A       = intf.A;
            s.B       = intf.B;
            s.op_code = intf.op_code;
            s.C_in    = intf.C_in;
            @(posedge intf.CLK);
            s.Result  = intf.Result;
            s.C_out   = intf.C_out;
            s.Z_flag  = intf.Z_flag;
            mon_ap.write(s);
        end
    endtask
endclass

`endif
