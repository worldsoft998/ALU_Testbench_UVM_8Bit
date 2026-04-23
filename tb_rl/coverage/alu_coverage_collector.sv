// ============================================================================
// alu_coverage_collector.sv - Functional coverage for the ALU
// ============================================================================
// Coverpoints mirror the Python-side coverage model in rl/coverage_model.py so
// that coverage feedback sent over the bridge is semantically identical to the
// coverage simulator reports.
// ============================================================================
`ifndef ALU_COVERAGE_COLLECTOR_SV
`define ALU_COVERAGE_COLLECTOR_SV

`uvm_analysis_imp_decl(_alu_cov)

class alu_coverage_collector extends uvm_component;
    `uvm_component_utils(alu_coverage_collector)

    uvm_analysis_imp_alu_cov #(alu_seq_item, alu_coverage_collector) analysis_export;

    // Public counters so the bridge can expose real-time coverage% to RL.
    int unsigned bins_total;
    int unsigned bins_hit;

    alu_seq_item sample_item;

    covergroup cg_alu;
        option.per_instance = 1;

        cp_reset : coverpoint sample_item.Reset;
        cp_cin   : coverpoint sample_item.C_in;

        cp_A : coverpoint sample_item.A {
            bins zero   = {8'h00};
            bins max    = {8'hFF};
            bins low    = {[8'h01:8'h3F]};
            bins mid    = {[8'h40:8'hBF]};
            bins high   = {[8'hC0:8'hFE]};
        }
        cp_B : coverpoint sample_item.B {
            bins zero   = {8'h00};
            bins max    = {8'hFF};
            bins low    = {[8'h01:8'h3F]};
            bins mid    = {[8'h40:8'hBF]};
            bins high   = {[8'hC0:8'hFE]};
        }
        cp_op : coverpoint sample_item.op_code {
            bins add  = {4'd0};
            bins sub  = {4'd1};
            bins mul  = {4'd2};
            bins div  = {4'd3};
            bins andd = {4'd4};
            bins xorr = {4'd5};
        }

        cx_op_A : cross cp_op, cp_A;
        cx_op_B : cross cp_op, cp_B;
        cx_AB   : cross cp_A, cp_B {
            bins corner_zero = binsof(cp_A.zero) && binsof(cp_B.zero);
            bins corner_max  = binsof(cp_A.max)  && binsof(cp_B.max);
            bins corner_mix  = (binsof(cp_A.zero) && binsof(cp_B.max)) ||
                               (binsof(cp_A.max)  && binsof(cp_B.zero));
        }
    endgroup

    function new(string name = "alu_coverage_collector", uvm_component parent = null);
        super.new(name, parent);
        cg_alu = new();
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        analysis_export = new("analysis_export", this);
    endfunction

    virtual function void write_alu_cov(alu_seq_item t);
        sample_item = t;
        cg_alu.sample();
        // Approximate hit accounting from the instance coverage.
        bins_total = 100; // real value: queried at report_phase via get_inst_coverage.
        bins_hit   = int'(cg_alu.get_inst_coverage());
    endfunction

    virtual function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        `uvm_info(get_type_name(),
            $sformatf("Functional coverage: %0.2f%%", cg_alu.get_inst_coverage()),
            UVM_NONE)
    endfunction
endclass

`endif
