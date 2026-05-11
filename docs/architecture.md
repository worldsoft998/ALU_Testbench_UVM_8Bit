# AIa-VO Architecture

## System Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                        AIa-VO Framework                             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │                  AI Verification Agent                       │    ║
║  │                  (agent.py - Orchestrator)                   │    ║
║  │                                                              │    ║
║  │  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │    ║
║  │  │ Coverage   │  │    Gap      │  │    Seed Manager      │ │    ║
║  │  │ Parser     │  │  Analyzer   │  │  (seed_manager.py)   │ │    ║
║  │  │            │  │             │  └──────────────────────┘ │    ║
║  │  └────────────┘  └─────────────┘                           │    ║
║  └─────────────────────────┬───────────────────────────────────┘    ║
║                            │                                         ║
║           ┌────────────────┼────────────────┐                       ║
║           ▼                ▼                ▼                        ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐        ║
║  │  LLM Layer   │ │  ML Layer    │ │ Simulation Interface │        ║
║  │              │ │              │ │                      │        ║
║  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────────────┐│        ║
║  │ │ OpenAI   │ │ │ │Bayesian  │ │ │ │   VCS Runner     ││        ║
║  │ ├──────────┤ │ │ ├──────────┤ │ │ │   (vcs_runner.py)││        ║
║  │ │ Gemini   │ │ │ │ RL Agent │ │ │ ├──────────────────┤│        ║
║  │ ├──────────┤ │ │ ├──────────┤ │ │ │   Log Monitor    ││        ║
║  │ │ Claude   │ │ │ │ Random   │ │ │ │  (log_monitor.py)││        ║
║  │ └──────────┘ │ │ │ Forest   │ │ │ ├──────────────────┤│        ║
║  │              │ │ ├──────────┤ │ │ │   Results DB     ││        ║
║  │ Prompt       │ │ │ Ensemble │ │ │ │  (results_db.py) ││        ║
║  │ Templates    │ │ ├──────────┤ │ │ └──────────────────┘│        ║
║  │              │ │ │ Neural   │ │ │                      │        ║
║  │              │ │ │ Net      │ │ │                      │        ║
║  │              │ │ └──────────┘ │ │                      │        ║
║  └──────────────┘ └──────────────┘ └───────────┬──────────┘        ║
║                                                 │                    ║
╚═════════════════════════════════════════════════╪════════════════════╝
                                                  │
                    SIMULATION BOUNDARY           │
                    (No TB Modification)           │
                                                  ▼
              ┌──────────────────────────────────────────┐
              │          Synopsys VCS Simulator           │
              │  +ntb_random_seed=N    -cm coverage      │
              ├──────────────────────────────────────────┤
              │                                          │
              │  ┌──────────────────────────────────┐    │
              │  │     Existing UVM Testbench        │    │
              │  │     (UNMODIFIED BLACK BOX)        │    │
              │  │                                    │    │
              │  │  Sequence → Driver → DUT → Monitor │    │
              │  │                    ↓               │    │
              │  │            Coverage Collector      │    │
              │  │              Scoreboard            │    │
              │  └──────────────────────────────────┘    │
              │                                          │
              └──────────────────────────────────────────┘
```

## Design Principles

### 1. Black-Box Testbench Treatment
The framework treats the existing UVM testbench as an opaque entity. All interaction occurs through:
- **VCS plusargs**: `+ntb_random_seed=N` controls randomization
- **Coverage database**: VCS generates coverage data parsed post-simulation
- **Simulation logs**: UVM output parsed for pass/fail and coverage info

### 2. Simulation Boundary Architecture
The AI operates exclusively at the simulation boundary:
- **Pre-simulation**: Selects optimal seed and configuration
- **Post-simulation**: Parses coverage reports and logs
- **Between runs**: Analyzes gaps, consults LLM/ML, selects next seed

### 3. Minimal Token LLM Usage
LLM is consulted only when needed (stagnation, complex gaps). Prompts use compressed JSON format for minimal token consumption while maximizing actionable output.

## Data Flow

```
Iteration N:
  1. ML Optimizer → suggest seed S_n
  2. VCS Runner → execute simulation with +ntb_random_seed=S_n
  3. Coverage Parser → parse coverage database / logs
  4. Coverage Merger → merge with cumulative coverage
  5. Gap Analyzer → identify uncovered bins, detect stagnation
  6. ML Optimizer → update model with (S_n, coverage_delta) observation
  7. [If stagnation] LLM → analyze gaps, suggest strategy
  8. Results DB → store iteration data
  9. Metrics → record coverage trend
  10. Check convergence → continue or stop
```

## Component Details

### Coverage Parser (`coverage_parser.py`)
- Parses VCS URG text reports
- Parses VCS simulation logs for UVM output
- Extracts coverage percentages per bin
- Merges multiple coverage reports

### Gap Analyzer (`gap_analyzer.py`)
- Maps uncovered bins to specific ALU input values
- Assigns priority scores to coverage gaps
- Detects coverage stagnation patterns
- Generates stimulus hints for AI optimization

### Bayesian Optimizer (`bayesian_opt.py`)
- Gaussian Process models seed→coverage mapping
- Expected Improvement acquisition for seed selection
- Incorporates LLM hints as candidate seeds

### RL Agent (`rl_agent.py`)
- Q-learning with discretized state/action spaces
- State: coverage percentage bucket (20 buckets)
- Action: seed range bucket (50 buckets)
- Reward: scaled coverage improvement

### VCS Runner (`vcs_runner.py`)
- Manages VCS compilation and simulation
- Passes seeds via `+ntb_random_seed`
- Collects coverage databases
- Supports coverage merging via URG

## Coverage Model

The ALU testbench defines the following coverage structure:

| Coverpoint | Bins | Description |
|------------|------|-------------|
| Reset | 0, 1 | Reset signal states |
| A | All_Ones, All_Zeros, random | Operand A boundary values |
| B | All_Ones, All_Zeros, random | Operand B boundary values |
| op_code | add, sub, mul, div, and, xor | All 6 ALU operations |
| C_in | 0, 1 | Carry-in values |
| corner_cases | 12 cross bins | A×B×op_code boundary combinations |

**Total bins**: ~28 individual + 12 cross = 40 coverage points
