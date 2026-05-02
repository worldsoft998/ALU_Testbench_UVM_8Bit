# AId-VO: AI-Directed Verification Optimization

## 8-bit ALU UVM Testbench with RL-based Coverage Acceleration

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Gymnasium](https://img.shields.io/badge/gymnasium-0.29+-green.svg)](https://gymnasium.farama.org/)
[![SB3](https://img.shields.io/badge/stable--baselines3-2.1+-orange.svg)](https://stable-baselines3.readthedocs.io/)

AId-VO uses **Reinforcement Learning** to accelerate functional coverage closure
for UVM-based hardware verification. It treats the simulation environment as a
**black box**, operating at the simulation boundary to observe coverage state and
steer stimulus generation — **without modifying any existing testbench code**.

## Key Features

- **Zero testbench modifications** — AI agents work purely through simulation
  seeds, plusargs, and log/coverage parsing
- **Multiple RL algorithms** — PPO, DQN, A2C via stable-baselines3
- **OpenAI Gymnasium environment** — Standard RL interface for the verification task
- **Python ALU model** — Train agents offline without VCS; deploy on VCS when ready
- **Automated comparison** — AI vs baseline with quantitative metrics
- **Synopsys VCS integration** — Makefile targets for compile, simulate, and coverage
- **Professional reporting** — Coverage traces, gap analysis, and comparison reports

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AId-VO System                        │
│                                                         │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │  RL Agent  │──▶│  Stimulus    │──▶│  Simulator   │  │
│  │ PPO/DQN/A2C│   │  Engine      │   │  (VCS or     │  │
│  │            │   │  seed, bias, │   │   Python)    │  │
│  │ observes   │   │  opcode wts  │   │              │  │
│  │ coverage   │   └──────────────┘   │  DUT + TB    │  │
│  │ state      │                      │  (UNCHANGED) │  │
│  └─────▲──────┘                      └──────┬───────┘  │
│        │                                     │          │
│        └──── Coverage Parser ◀───────────────┘          │
│              (logs, reports, Python model)               │
└─────────────────────────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for detailed system design.

## Repository Structure

```
├── DUT/                        # RTL source (UNCHANGED)
│   ├── ALU_DUT.sv              #   8-bit ALU implementation
│   └── ALU_interface.sv        #   Signal interface
│
├── Testbench/                  # UVM testbench (UNCHANGED)
│   ├── ALU_pkg.sv              #   Package with all TB components
│   ├── ALU_Top.sv              #   Top-level module
│   ├── ALU_Sequence_Item.sv    #   Transaction definition
│   ├── ALU_Sequence.sv         #   Test/reset sequences
│   ├── ALU_Sequencer.sv        #   Sequencer
│   ├── ALU_Driver.sv           #   Pin-level driver
│   ├── ALU_monitor.sv          #   Transaction monitor
│   ├── ALU_Scoreboard.sv       #   Reference model checker
│   ├── ALU_Coverage_Collector.sv  # Functional coverage
│   ├── ALU_Agent.sv            #   UVM agent
│   ├── ALU_Env.sv              #   UVM environment
│   └── Test.sv                 #   Test class
│
├── ai/                         # AI/RL modules (Python)
│   ├── core/
│   │   ├── config.py           #   Configuration management
│   │   └── orchestrator.py     #   Main verification loop
│   ├── environments/
│   │   ├── alu_coverage_env.py #   Gymnasium RL environment
│   │   └── alu_sim_model.py    #   Python ALU + coverage model
│   ├── agents/
│   │   └── coverage_agent.py   #   PPO, DQN, A2C agents
│   ├── parsers/
│   │   ├── vcs_log_parser.py   #   VCS simulation log parser
│   │   └── coverage_parser.py  #   Unified coverage parser
│   ├── generators/
│   │   ├── seed_optimizer.py   #   Seed selection strategies
│   │   └── stimulus_generator.py  # Stimulus directive engine
│   ├── analysis/
│   │   ├── comparator.py       #   AI vs baseline comparison
│   │   └── reporter.py         #   Report generation
│   ├── train.py                #   Training script
│   ├── evaluate.py             #   Evaluation script
│   └── run_comparison.py       #   Full comparison script
│
├── scripts/                    # Shell scripts
│   ├── run_vcs.sh              #   Single VCS simulation run
│   ├── run_ai_verification.sh  #   AI-directed verification flow
│   └── run_comparison.sh       #   Quick comparison runner
│
├── tests/                      # Python unit tests
│   └── test_rl_stack.py        #   Comprehensive test suite
│
├── docs/                       # Documentation
│   ├── architecture.md         #   System architecture
│   └── user_guide.md           #   User guide
│
├── Makefile                    # Build & run targets
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Python project metadata
└── README.md                   # This file
```

## Quick Start

### Prerequisites
- Python 3.9+
- (Optional) Synopsys VCS with UVM-1.2

### Installation

```bash
pip install -r requirements.txt
```

### Smoke Test

```bash
make py-smoke
```

### Train an RL Agent

```bash
# Default (PPO)
make train

# Specific algorithm
make train AI_ALGORITHM=dqn AI_TIMESTEPS=30000

# All three
make train-ppo && make train-dqn && make train-a2c
```

### Full AI vs Baseline Comparison

```bash
make compare
```

### Generate Report

```bash
make report
```

## ALU Design

The 8-bit ALU supports six operations:

| Opcode | Operation | Description |
|--------|-----------|-------------|
| 0000 | ADD | A + B + C_in |
| 0001 | SUB | A − B |
| 0010 | MULT | A × B |
| 0011 | DIV | A ÷ B |
| 0100 | AND | A & B |
| 0101 | XOR | A ^ B |

**Ports**: 8-bit operands A, B; 4-bit op_code; carry-in C_in; 16-bit Result;
carry-out C_out; zero flag Z_flag.

## Coverage Model (28 Bins)

| Group | Bins | Description |
|-------|------|-------------|
| A | All_Ones, All_Zeros, random | Operand A boundary values |
| B | All_Ones, All_Zeros, random | Operand B boundary values |
| op_code | add, sub, mul, div, and, xor | All 6 operations |
| C_in | 0, 1 | Carry input |
| Reset | 0, 1 | Reset state |
| corner_cases | 12 cross bins | A×B×op for boundary combos |

## AI/RL Approach

### RL Formulation

| Component | Definition |
|-----------|------------|
| **State** | 28 coverage bin flags + overall coverage % + normalised step counter |
| **Action** | Composite: seed_bucket × operand_bias × opcode_focus × batch_scale |
| **Reward** | +10 × Δcoverage, +0.5 per new corner-case bin, −0.1 step cost, +50 at target |
| **Episode** | Ends when coverage target reached or max iterations exhausted |

### How It Works

1. **Training Phase**: RL agent trains on the Python ALU model (fast, no VCS needed)
2. **Deployment Phase**: Trained agent selects optimal simulation parameters
3. **Each Iteration**:
   - Agent observes current coverage state
   - Agent decides: seed region, operand bias, opcode focus, batch size
   - Parameters translated to VCS plusargs (or Python model input)
   - Simulation runs, coverage is updated
4. **Result**: Faster coverage closure with fewer transactions

### Zero-Delay Integration

The AI operates synchronously with the simulation loop:
- **Inputs** to AI: coverage state vectors parsed from simulation output
- **Outputs** from AI: `+ntb_random_seed=N` and other VCS plusargs
- **No testbench modification**: the AI only controls what the simulator's
  standard interfaces already expose

## VCS Simulation

### Single Run

```bash
make sim TEST=ALU_Test SEED=42 VERBOSITY=UVM_LOW
```

### With Coverage

```bash
make sim-coverage SEED=42
```

### AI-Directed Verification

```bash
make sim-ai AI_ALGORITHM=ppo SIM_MODE=vcs
```

## Makefile Targets

| Target | Description | VCS Required |
|--------|-------------|:------------:|
| `help` | Show all targets and variables | No |
| `install` | Install Python dependencies | No |
| `py-smoke` | Quick RL stack smoke test | No |
| `test` | Run Python unit tests | No |
| `train` | Train RL agent | No |
| `train-ppo` | Train PPO agent | No |
| `train-dqn` | Train DQN agent | No |
| `train-a2c` | Train A2C agent | No |
| `evaluate` | Evaluate agent vs baseline | No |
| `compare` | Full multi-algorithm comparison | No |
| `report` | Generate comparison report | No |
| `sim` | Single VCS simulation | Yes |
| `sim-compile` | VCS compile only | Yes |
| `sim-run` | VCS run only | Yes |
| `sim-coverage` | VCS with coverage | Yes |
| `sim-ai` | AI-directed VCS verification | Yes |
| `sim-baseline` | Baseline VCS run | Yes |
| `clean` | Remove build artifacts | No |
| `zip` | Create distributable archive | No |

## UVM Testbench

The UVM testbench structure follows standard methodology:

```
ALU_Test
  └── ALU_Env
        ├── ALU_Agent
        │     ├── ALU_Sequencer
        │     ├── ALU_Driver
        │     └── ALU_monitor
        ├── ALU_Scoreboard
        └── ALU_Coverage_Collector
```

## Original UVM Testbench Structure
<img src="Img/uvm_mem_model_block_diagram (1).png" width="500">

## Original Report Summary
<img src="Img/final_report.png" width="1000">

## Original Testbench Components
<img src="Img/testbench_structure.png" width="1000">

## Original Coverage Results
<img src="Img/cov1.png" width="1000">
<img src="Img/cov2.png" width="1000">
<img src="Img/cov3.png" width="1000">

## License

MIT
