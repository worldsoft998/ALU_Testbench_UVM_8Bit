# AId-VO Architecture

## AI-Directed Verification Optimization for 8-bit ALU UVM Testbench

### Design Philosophy

AId-VO operates **at the simulation boundary** — it observes simulation outputs
(logs, coverage reports) and controls simulation inputs (random seeds, plusargs)
without modifying any existing testbench or DUT source files.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AId-VO System                                │
│                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐    │
│  │  RL Agent    │────▶│  Stimulus    │────▶│  VCS Simulator   │    │
│  │  (PPO/DQN/  │     │  Engine      │     │  ┌────────────┐  │    │
│  │   A2C)      │     │              │     │  │ DUT (ALU)  │  │    │
│  │             │     │  • Seed      │     │  └────────────┘  │    │
│  │  Observes:  │     │  • Opcode    │     │  ┌────────────┐  │    │
│  │  • Coverage │     │    weights   │     │  │ UVM TB     │  │    │
│  │  • Bins hit │     │  • Operand   │     │  │ (UNCHANGED)│  │    │
│  │  • Progress │     │    bias      │     │  └────────────┘  │    │
│  │             │     │  • Batch     │     │                  │    │
│  │  Decides:   │     │    size      │     │  Outputs:        │    │
│  │  • Next     │     │              │     │  • sim.log       │    │
│  │    action   │     │  Generates:  │     │  • coverage.db   │    │
│  └──────┬───────┘     │  • VCS       │     │  • urgReport     │    │
│         │             │    plusargs  │     └────────┬─────────┘    │
│         │             │  • Seed file │              │              │
│         │             └──────────────┘              │              │
│         │                                           │              │
│  ┌──────┴──────────────────────────────────────────┴───────────┐  │
│  │                    Coverage Parser                           │  │
│  │                                                              │  │
│  │  • VCS log parser     → transaction extraction               │  │
│  │  • Coverage report    → bin-level coverage state             │  │
│  │  • Python model       → fast offline training                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### System Components

#### 1. RL Environment (`ai/environments/`)

**`ALUCoverageEnv`** — Gymnasium environment wrapping the ALU verification task.

| Property | Detail |
|----------|--------|
| Observation | 30-d vector: 28 coverage bin flags + overall coverage + normalised step |
| Action | Discrete(420): seed_bucket × operand_bias × opcode_focus × batch_scale |
| Reward | +10 × coverage_delta, +0.5 per corner-case bin, −0.1 step cost, +50 at target |
| Episode | Terminates when target coverage reached or max steps exhausted |

**`ALUModel`** / **`CoverageModel`** — Python functional models of the DUT and
coverage collector, enabling RL training without VCS.

#### 2. RL Agents (`ai/agents/`)

**`CoverageAgent`** — Unified interface over stable-baselines3 algorithms:

| Algorithm | Type | Best For |
|-----------|------|----------|
| **PPO** | On-policy, actor-critic | General-purpose, stable training |
| **DQN** | Off-policy, value-based | Sample-efficient, replay-buffer learning |
| **A2C** | On-policy, actor-critic | Fast training, multi-threaded sampling |

**`RandomBaselineAgent`** — Non-AI baseline using purely random actions, providing
the comparison benchmark.

#### 3. Parsers (`ai/parsers/`)

- **`VCSLogParser`** — Extracts transaction data, error counts, and coverage from
  VCS simulation logs (works with unmodified UVM output).
- **`VCSCoverageReportParser`** — Parses URG coverage reports.
- **`UnifiedCoverageParser`** — Abstraction layer producing `CoverageSnapshot`
  objects from either VCS or Python data sources.

#### 4. Generators (`ai/generators/`)

- **`SeedOptimizer`** — Tracks seed→coverage mappings, suggests seeds using
  gap-targeted, replay-best, and exploration strategies.
- **`AIDirectedStimulusEngine`** — Translates RL actions into `SimulationDirective`
  objects containing VCS plusargs and transaction parameters.

#### 5. Orchestrator (`ai/core/orchestrator.py`)

Central coordination loop:

```
for iteration in range(max_iterations):
    1. Agent observes coverage state
    2. Agent selects action
    3. Engine creates SimulationDirective
    4. Directive executed (Python model or VCS)
    5. Coverage parsed and fed back
    6. Check termination (target reached?)
```

#### 6. Analysis (`ai/analysis/`)

- **`VerificationComparator`** — Computes quantitative metrics between runs.
- **`ReportGenerator`** — Produces markdown reports with coverage traces.

### Coverage Bin Map (28 bins)

```
Index  Bin Name          UVM Covergroup Source
─────  ────────────────  ─────────────────────────────
 0-2   A_*               coverpoint item.A
 3-5   B_*               coverpoint item.B
 6-11  op_*              coverpoint item.op_code
12-13  C_in_*            coverpoint item.C_in
14-15  Reset_*           coverpoint item.Reset
16-27  {Op}_cross{1,2}   cross A, B, op_code (corner_cases)
```

### Data Flow: VCS Mode

```
Python AI Agent
    │
    ├──▶ SimulationDirective
    │        seed=42, opcode_weights=[...], operand_bias="boundary"
    │
    ├──▶ VCS plusargs
    │        +ntb_random_seed=42
    │        +AI_OP_WEIGHT_0=0.2000
    │        +AI_OPERAND_BIAS=boundary
    │
    ├──▶ VCS Simulation (Testbench UNCHANGED)
    │        vcs ... +ntb_random_seed=42 -cm line+cond+fsm+branch+tgl
    │
    ├──◀ Simulation Log + Coverage Report
    │
    └──▶ Parser → CoverageSnapshot → RL observation
```

### Data Flow: Python Model Mode

```
Python AI Agent
    │
    ├──▶ Action (seed_bucket, operand_bias, opcode_focus, batch_size)
    │
    ├──▶ StimulusGenerator.generate_biased()
    │        → list[ALUTransaction]
    │
    ├──▶ PythonSimRunner.run_batch()
    │        ALUModel.execute() + CoverageModel.sample()
    │
    └──▶ CoverageModel.get_state_vector() → RL observation
```
