// ============================================================================
// alu_seq_item.sv - Sequence item for the 8-bit ALU agent
// ============================================================================
// Transaction object carrying operands, op-code and observed DUT response.
// Randomisation constraints bias values toward corner cases while still
// allowing a uniform fallback, which keeps random-baseline runs meaningful.
// ============================================================================
`ifndef ALU_SEQ_ITEM_SV
`define ALU_SEQ_ITEM_SV

class alu_seq_item extends uvm_sequence_item;
    `uvm_object_utils(alu_seq_item)

    // ----- stimulus fields -----
    rand bit          Reset;
    rand bit [7:0]    A;
    rand bit [7:0]    B;
    rand bit [3:0]    op_code;
    rand bit          C_in;

    // ----- observed response fields (written by monitor) -----
    bit [15:0]        Result;
    bit               C_out;
    bit               Z_flag;

    // ----- tag fields -----
    bit               from_rl;   // set when item came from RL agent
    int               gen_id;    // generator-side correlation id

    constraint c_op_code {
        op_code inside {[0:5]};
    }

    // Distribution keeps corners frequent but still covers the mid-range.
    constraint c_data_A {
        A dist { 8'hFF := 20, 8'h00 := 20, [8'h01:8'hFE] := 60 };
    }
    constraint c_data_B {
        B dist { 8'hFF := 20, 8'h00 := 20, [8'h01:8'hFE] := 60 };
    }

    constraint c_reset_default {
        soft Reset == 1'b0;
    }

    function new(string name = "alu_seq_item");
        super.new(name);
    endfunction

    virtual function void do_copy(uvm_object rhs);
        alu_seq_item that;
        if (!$cast(that, rhs)) begin
            `uvm_fatal(get_type_name(), "do_copy: cast failed")
            return;
        end
        super.do_copy(rhs);
        Reset   = that.Reset;
        A       = that.A;
        B       = that.B;
        op_code = that.op_code;
        C_in    = that.C_in;
        Result  = that.Result;
        C_out   = that.C_out;
        Z_flag  = that.Z_flag;
        from_rl = that.from_rl;
        gen_id  = that.gen_id;
    endfunction

    virtual function string convert2string();
        return $sformatf("rst=%0b op=%0d A=0x%02h B=0x%02h Cin=%0b -> Res=0x%04h Cout=%0b Z=%0b rl=%0b id=%0d",
            Reset, op_code, A, B, C_in, Result, C_out, Z_flag, from_rl, gen_id);
    endfunction
endclass

`endif
