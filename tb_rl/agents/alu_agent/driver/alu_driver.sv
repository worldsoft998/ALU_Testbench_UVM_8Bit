// ============================================================================
// alu_driver.sv - Drives stimulus on the ALU interface
// ============================================================================
// One item = one clock cycle of stimulus. Reset is driven synchronously on
// the DUT. The driver keeps a transaction count for scoreboard debugging.
// ============================================================================
`ifndef ALU_DRIVER_SV
`define ALU_DRIVER_SV

class alu_driver extends uvm_driver #(alu_seq_item);
    `uvm_component_utils(alu_driver)

    virtual ALU_interface intf;
    int unsigned          num_items;

    function new(string name = "alu_driver", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual ALU_interface)::get(this, "", "intf", intf))
            `uvm_fatal(get_type_name(), "virtual ALU_interface not found")
    endfunction

    virtual task run_phase(uvm_phase phase);
        alu_seq_item item;
        // Hold reset for a few cycles to let the DUT initialise.
        intf.Reset   <= 1'b1;
        intf.A       <= 8'h00;
        intf.B       <= 8'h00;
        intf.op_code <= 4'h0;
        intf.C_in    <= 1'b0;
        repeat (3) @(posedge intf.CLK);
        intf.Reset   <= 1'b0;

        forever begin
            seq_item_port.get_next_item(item);
            drive(item);
            num_items++;
            seq_item_port.item_done();
        end
    endtask

    virtual task drive(alu_seq_item item);
        @(posedge intf.CLK);
        intf.Reset   <= item.Reset;
        intf.A       <= item.A;
        intf.B       <= item.B;
        intf.op_code <= item.op_code;
        intf.C_in    <= item.C_in;
    endtask
endclass

`endif
