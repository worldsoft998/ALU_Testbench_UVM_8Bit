// ============================================================================
// alu_agent.sv - Active UVM agent: sequencer + driver + monitor
// ============================================================================
`ifndef ALU_AGENT_SV
`define ALU_AGENT_SV

class alu_agent extends uvm_agent;
    `uvm_component_utils(alu_agent)

    alu_sequencer sqr;
    alu_driver    drv;
    alu_monitor   mon;

    // Re-exported analysis port so env components can connect at one place.
    uvm_analysis_port #(alu_seq_item) ap;

    function new(string name = "alu_agent", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        sqr = alu_sequencer::type_id::create("sqr", this);
        drv = alu_driver   ::type_id::create("drv", this);
        mon = alu_monitor  ::type_id::create("mon", this);
        ap  = new("ap", this);
    endfunction

    virtual function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        drv.seq_item_port.connect(sqr.seq_item_export);
        mon.mon_ap.connect(ap);
    endfunction
endclass

`endif
