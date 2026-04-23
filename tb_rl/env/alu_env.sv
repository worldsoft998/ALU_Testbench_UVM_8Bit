// ============================================================================
// alu_env.sv - Top-level UVM environment
// ============================================================================
// Instantiates the agent, scoreboard and coverage collector and connects the
// agent's analysis port to both subscribers. The RL bridge component is
// conditionally created based on the config_db flag "use_rl".
// ============================================================================
`ifndef ALU_ENV_SV
`define ALU_ENV_SV

class alu_env extends uvm_env;
    `uvm_component_utils(alu_env)

    alu_agent                 agent;
    alu_scoreboard            scb;
    alu_coverage_collector    cov;
    alu_rl_bridge             bridge;

    bit use_rl;

    function new(string name = "alu_env", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        void'(uvm_config_db#(bit)::get(this, "", "use_rl", use_rl));

        agent = alu_agent            ::type_id::create("agent", this);
        scb   = alu_scoreboard       ::type_id::create("scb",   this);
        cov   = alu_coverage_collector::type_id::create("cov",   this);

        if (use_rl)
            bridge = alu_rl_bridge   ::type_id::create("bridge", this);
    endfunction

    virtual function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        agent.ap.connect(scb.obs_imp);
        agent.ap.connect(cov.analysis_export);
        if (use_rl) begin
            agent.ap.connect(bridge.obs_imp);
            bridge.set_sequencer(agent.sqr);
            bridge.set_scoreboard(scb);
            bridge.set_coverage(cov);
        end
    endfunction
endclass

`endif
