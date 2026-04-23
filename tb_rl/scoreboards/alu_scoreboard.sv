// ============================================================================
// alu_scoreboard.sv - Golden-reference scoreboard for the ALU
// ============================================================================
// Receives observed transactions, recomputes the expected outputs from a
// pure-SystemVerilog reference model, and reports mismatches. A running
// pass/fail count is surfaced for report_phase.
// ============================================================================
`ifndef ALU_SCOREBOARD_SV
`define ALU_SCOREBOARD_SV

`uvm_analysis_imp_decl(_alu_obs)

class alu_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(alu_scoreboard)

    uvm_analysis_imp_alu_obs #(alu_seq_item, alu_scoreboard) obs_imp;

    int unsigned n_total;
    int unsigned n_pass;
    int unsigned n_fail;

    // Optional hook: a bridge component polls these to forward responses.
    bit          last_valid;
    alu_seq_item last_item;
    bit          last_mismatch;

    function new(string name = "alu_scoreboard", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        obs_imp = new("obs_imp", this);
    endfunction

    // The reference model - small, readable, matches the DUT.
    function void predict(input alu_seq_item t,
                          output bit [15:0] exp_result,
                          output bit        exp_cout,
                          output bit        exp_zflag);
        bit [15:0] r;
        r = 16'h0000;
        case (t.op_code)
            4'd0: begin r = t.A + t.B + t.C_in; exp_cout = r[8]; end
            4'd1: begin r = t.A - t.B;          exp_cout = r[8]; end
            4'd2: begin r = t.A * t.B;          exp_cout = 1'b0; end
            4'd3: begin r = (t.B == 0) ? 16'h0 : (t.A / t.B); exp_cout = 1'b0; end
            4'd4: begin r = t.A & t.B;          exp_cout = 1'b0; end
            4'd5: begin r = t.A ^ t.B;          exp_cout = 1'b0; end
            default: begin r = 16'h0; exp_cout = 1'b0; end
        endcase
        exp_result = r;
        exp_zflag  = (r == 16'h0);
    endfunction

    virtual function void write_alu_obs(alu_seq_item t);
        bit [15:0] exp_result;
        bit        exp_cout;
        bit        exp_zflag;
        bit        mismatch;

        if (t.Reset) begin
            last_valid    = 1'b1;
            last_item     = t;
            last_mismatch = 1'b0;
            return;
        end

        predict(t, exp_result, exp_cout, exp_zflag);

        mismatch = !((exp_result == t.Result) &&
                     (exp_cout   == t.C_out)  &&
                     (exp_zflag  == t.Z_flag));

        n_total++;
        if (mismatch) begin
            n_fail++;
            `uvm_error(get_type_name(),
                $sformatf("MISMATCH op=%0d A=0x%02h B=0x%02h Cin=%0b | got Res=0x%04h Cout=%0b Z=%0b | exp Res=0x%04h Cout=%0b Z=%0b",
                          t.op_code, t.A, t.B, t.C_in,
                          t.Result, t.C_out, t.Z_flag,
                          exp_result, exp_cout, exp_zflag))
        end else begin
            n_pass++;
        end

        last_valid    = 1'b1;
        last_item     = t;
        last_mismatch = mismatch;
    endfunction

    virtual function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        `uvm_info(get_type_name(),
            $sformatf("Scoreboard summary: total=%0d pass=%0d fail=%0d", n_total, n_pass, n_fail),
            UVM_NONE)
    endfunction
endclass

`endif
