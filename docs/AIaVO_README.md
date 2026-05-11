# AIa-VO: AI Agent Supported Verification Optimization

**An Automated Universal RTL Verification Acceleration Framework using LLM Agents**

## Overview

AIa-VO is an AI-enhanced hardware RTL verification acceleration framework that integrates AI agents into the simulation flow for intelligent, dynamic coverage-driven verification optimization. It operates at the **simulation boundary** without modifying existing testbenches, treating the verification environment as a black box.

### Key Features

- **Zero testbench modification** — works with any existing UVM/SV testbench
- **Multi-LLM support** — OpenAI GPT, Google Gemini, Anthropic Claude
- **Multiple ML algorithms** — Bayesian optimization, Reinforcement Learning, Random Forest, Ensemble
- **Real-time coverage analysis** — parses VCS coverage reports and simulation logs
- **Intelligent seed selection** — AI-driven seed optimization for faster coverage closure
- **Stagnation detection** — automatically detects and responds to coverage plateaus
- **Comparison framework** — built-in AI vs. baseline benchmarking
- **Synopsys VCS integration** — full Makefile and scripts for VCS simulation

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIa-VO Agent Loop                            │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Select   │───▶│   Run    │───▶│  Parse   │───▶│ Analyze  │  │
│  │   Seed    │    │   VCS    │    │ Coverage │    │   Gaps   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       ▲                                               │         │
│       │          ┌──────────┐    ┌──────────┐         │         │
│       └──────────│  ML/RL   │◀───│   LLM    │◀────────┘         │
│                  │ Optimize │    │ Consult  │                   │
│                  └──────────┘    └──────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │  Existing Testbench │  ◀── NOT MODIFIED
              │  (Black Box)        │
              └─────────────────────┘
```

The AI agent:
1. Runs VCS simulations with AI-selected random seeds (`+ntb_random_seed=N`)
2. Parses coverage reports to identify functional coverage gaps
3. Uses LLM to analyze gap patterns and suggest stimulus strategies
4. Uses ML models (RL/Bayesian/RF) to predict optimal seeds
5. Iterates until target coverage is reached or convergence detected

## Quick Start

### Prerequisites

- **Synopsys VCS** (with UVM 1.2 support)
- **Python 3.9+**
- **LLM API key** (at least one of: OpenAI, Gemini, Claude)

### Installation

```bash
# Install Python dependencies
make install-deps

# Or manually:
pip install -r requirements.txt

# Set your LLM API key
export OPENAI_API_KEY="your-key-here"
# Or: export GEMINI_API_KEY="your-key" / export ANTHROPIC_API_KEY="your-key"
```

### Running

```bash
# Run AI-guided verification (default: Bayesian + OpenAI)
make ai

# Run with specific ML and LLM choices
make ai ML_ALGO=rl LLM=claude

# Run baseline (no AI) for comparison
make baseline

# Run single simulation with specific seed
make sim SEED=42 NUM_ITEMS=10000

# Run comparison (AI vs baseline)
make compare
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make help` | Show all targets and options |
| `make compile` | Compile design with VCS |
| `make sim` | Run single VCS simulation |
| `make ai` | Run AI-guided verification |
| `make baseline` | Run baseline regression (no AI) |
| `make compare` | Run AI + baseline comparison |
| `make report` | Generate reports from results |
| `make py-smoke` | Run Python unit tests |
| `make clean` | Clean simulation work directory |
| `make zip` | Create project archive |

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEED` | random | Simulation random seed |
| `NUM_ITEMS` | 5000 | Transactions per simulation |
| `LLM` | openai | LLM provider (openai/gemini/claude) |
| `ML_ALGO` | bayesian | ML algorithm (bayesian/rl/rf/ensemble) |
| `TARGET_COV` | 100.0 | Target coverage percentage |
| `MAX_ITER` | 50 | Maximum AI iterations |
| `BASELINE_RUNS` | 10 | Number of baseline runs |
| `COVERAGE` | 1 | Enable coverage (0/1) |
| `GUI` | 0 | Launch DVE waveform viewer (0/1) |

## Project Structure

```
ALU-Testbench-UVM-8Bit/
├── DUT/                          # RTL Design (UNMODIFIED)
│   ├── ALU_DUT.sv                #   8-bit ALU implementation
│   └── ALU_interface.sv          #   Signal interface
├── Testbench/                    # UVM Testbench (UNMODIFIED)
│   ├── ALU_pkg.sv                #   Package with all includes
│   ├── ALU_Top.sv                #   Top-level module
│   ├── ALU_Sequence_Item.sv      #   Transaction definition
│   ├── ALU_Sequence.sv           #   Test sequences
│   ├── ALU_Driver.sv             #   Pin-level driver
│   ├── ALU_monitor.sv            #   Transaction monitor
│   ├── ALU_Scoreboard.sv         #   Result checker
│   ├── ALU_Coverage_Collector.sv #   Functional coverage
│   ├── ALU_Agent.sv              #   Agent wrapper
│   ├── ALU_Env.sv                #   Environment
│   ├── ALU_Sequencer.sv          #   Sequencer
│   └── Test.sv                   #   Test class
├── ai_agent/                     # AI Verification Framework
│   ├── __init__.py
│   ├── __main__.py               #   python -m ai_agent entry
│   ├── cli.py                    #   Command-line interface
│   ├── core/                     #   Core engine
│   │   ├── agent.py              #     Main orchestrator
│   │   ├── config.py             #     Configuration management
│   │   ├── coverage_parser.py    #     VCS coverage parsing
│   │   └── gap_analyzer.py       #     Coverage gap analysis
│   ├── llm/                      #   LLM Integration
│   │   ├── base.py               #     Abstract LLM client
│   │   ├── openai_client.py      #     OpenAI GPT
│   │   ├── gemini_client.py      #     Google Gemini
│   │   ├── claude_client.py      #     Anthropic Claude
│   │   └── prompt_templates.py   #     Optimized prompts
│   ├── ml/                       #   ML Models
│   │   ├── rl_agent.py           #     Reinforcement Learning
│   │   ├── bayesian_opt.py       #     Bayesian Optimization
│   │   ├── seed_predictor.py     #     Random Forest predictor
│   │   └── coverage_model.py     #     Neural net predictor
│   ├── simulation/               #   Simulation Interface
│   │   ├── vcs_runner.py         #     VCS compile/run
│   │   ├── seed_manager.py       #     Seed generation
│   │   ├── log_monitor.py        #     Log monitoring
│   │   └── results_db.py         #     Results storage
│   └── comparison/               #   Comparison Framework
│       ├── metrics.py            #     Metrics collection
│       └── report_gen.py         #     Report generation
├── config/                       #   Configuration Files
│   ├── default.yaml              #     Default settings
│   └── advanced.yaml             #     Aggressive optimization
├── scripts/                      #   Simulation Scripts
│   ├── run_vcs.sh                #     VCS runner
│   ├── run_baseline.sh           #     Baseline regression
│   ├── run_ai_guided.sh          #     AI-guided runner
│   └── merge_coverage.sh         #     Coverage merge utility
├── tests/                        #   Unit Tests
│   ├── test_coverage_parser.py
│   ├── test_gap_analyzer.py
│   ├── test_seed_predictor.py
│   └── test_rl_stack.py          #     Integration test
├── docs/                         #   Documentation
│   ├── AIaVO_README.md           #     This file
│   ├── architecture.md           #     Architecture details
│   ├── user_guide.md             #     User guide
│   └── api_reference.md          #     API reference
├── Makefile                      #   Build & run targets
├── requirements.txt              #   Python dependencies
└── pyproject.toml                #   Project metadata
```

## ML Algorithms

### Bayesian Optimization (Default)
Uses a Gaussian Process to model the relationship between seed values and coverage improvement. Balances exploration vs. exploitation via Expected Improvement acquisition function.

### Reinforcement Learning
Q-learning agent that discretizes the coverage state and seed space. Learns which seed ranges produce the best coverage improvement through reward feedback.

### Random Forest
Trains a Random Forest regressor on historical seed→coverage mappings. Extracts structural features from seed values to predict coverage outcomes.

### Ensemble
Combines all three methods with weighted voting. Provides the most robust optimization across diverse coverage landscapes.

## LLM Integration

The LLM is consulted when:
- Coverage stagnation is detected (no improvement for N iterations)
- Complex corner cases remain uncovered
- Initial exploration phase needs strategic guidance

Prompts are optimized for minimal token usage while maximizing actionable output. The LLM receives compressed coverage data and returns structured JSON with seed suggestions and strategy recommendations.

## Architecture

See [architecture.md](architecture.md) for detailed architecture documentation.

## License

MIT
