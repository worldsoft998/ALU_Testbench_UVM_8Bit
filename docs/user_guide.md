# AIa-VO User Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Basic Usage](#basic-usage)
4. [Configuration](#configuration)
5. [LLM Setup](#llm-setup)
6. [ML Algorithm Selection](#ml-algorithm-selection)
7. [Running Comparisons](#running-comparisons)
8. [Interpreting Results](#interpreting-results)
9. [Advanced Usage](#advanced-usage)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- **Synopsys VCS** (2020.03 or later recommended) with UVM 1.2
- **Python 3.9+** with pip
- **URG** (Unified Report Generator, bundled with VCS)

### Environment Setup
```bash
# Ensure VCS is in PATH
which vcs    # Should return path to VCS binary
which urg    # Should return path to URG binary

# Set VCS_HOME if needed
export VCS_HOME=/path/to/vcs
export PATH=$VCS_HOME/bin:$PATH
```

## Installation

```bash
# Clone or extract the project
cd ALU-Testbench-UVM-8Bit

# Install Python dependencies
make install-deps
# Or: pip install -r requirements.txt

# Verify installation
make py-smoke
```

## Basic Usage

### Single Simulation (No AI)
```bash
# Run with random seed
make sim

# Run with specific seed
make sim SEED=42

# Run with custom transaction count
make sim SEED=42 NUM_ITEMS=10000

# Run with waveform viewer
make sim SEED=42 GUI=1
```

### AI-Guided Verification
```bash
# Default: Bayesian optimization + OpenAI GPT
make ai

# With specific LLM
make ai LLM=claude

# With specific ML algorithm
make ai ML_ALGO=rl

# Custom iteration limit
make ai MAX_ITER=20 NUM_ITEMS=3000

# Without LLM (ML-only mode)
python -m ai_agent.cli --no-llm

# Without ML (LLM-only mode)
python -m ai_agent.cli --no-ml
```

### Baseline Regression
```bash
# Run 10 baseline simulations
make baseline

# Custom number of runs
make baseline BASELINE_RUNS=20
```

### Comparison
```bash
# Run AI-guided + baseline and compare
make compare
```

## Configuration

### YAML Configuration
Edit `config/default.yaml` to customize settings:

```yaml
# Target coverage
target_coverage: 100.0
max_iterations: 50

# LLM settings
llm:
  provider: "openai"       # openai, gemini, claude
  model: "gpt-4o-mini"     # Model name
  max_tokens: 1024          # Max response tokens
  temperature: 0.3          # Sampling temperature

# ML settings
ml:
  algorithm: "bayesian"     # bayesian, rl, random_forest, ensemble
  rl_learning_rate: 0.01
  bayesian_acquisition: "ei"

# Simulation
simulation:
  default_num_items: 5000
  timeout_ns: 10000000
```

### Advanced Configuration
Use `config/advanced.yaml` for aggressive optimization:
```bash
make ai CONFIG_FILE=config/advanced.yaml
```

## LLM Setup

### OpenAI
```bash
export OPENAI_API_KEY="sk-..."
make ai LLM=openai
```

### Google Gemini
```bash
export GEMINI_API_KEY="..."
make ai LLM=gemini
```

### Anthropic Claude
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
make ai LLM=claude
```

### Running Without LLM
If no API key is available, the framework automatically disables LLM features and relies solely on ML optimization:
```bash
make ai  # Will warn about missing API key but continue with ML-only
```

## ML Algorithm Selection

| Algorithm | Best For | Speed | Accuracy |
|-----------|----------|-------|----------|
| `bayesian` | General use, small iteration budgets | Medium | High |
| `rl` | Long runs, learning from patterns | Slow start | Improves over time |
| `random_forest` | Historical data reuse | Fast | Medium |
| `ensemble` | Maximum coverage, any budget | Medium | Highest |

```bash
# Examples
make ai ML_ALGO=bayesian   # Good default
make ai ML_ALGO=rl         # Best for long runs
make ai ML_ALGO=ensemble   # Best overall accuracy
```

## Running Comparisons

The comparison framework runs AI-guided and baseline simulations with the same number of iterations and compares:

```bash
make compare
```

**Output**: `results/comparison_report.md` and `results/comparison_report.json`

### Metrics Compared
- **Final coverage**: Coverage achieved after N iterations
- **Coverage trend**: Coverage at each iteration step
- **Speedup**: Iterations needed to reach coverage targets (50%, 75%, 90%, 95%)
- **AUC**: Area under coverage curve (higher = faster convergence)

## Interpreting Results

### Coverage Report
After running, check `results/`:
- `ai_guided_report.md` — Markdown report with coverage trend
- `ai_guided_report.json` — Machine-readable results
- `comparison_report.md` — AI vs. baseline comparison

### Coverage Trend
```
Iter   1:  32.50% |#############
Iter   2:  55.00% |######################
Iter   3:  72.50% |#############################
Iter   4:  87.50% |###################################
Iter   5: 100.00% |########################################
```

### Session Data
Detailed per-iteration data is stored in `results/<session_id>/`:
- `iterations.csv` — CSV with per-iteration metrics
- `iter_NNNN.json` — Detailed coverage and gap analysis per iteration
- `summary.json` — Final summary

## Advanced Usage

### Python API
```python
from ai_agent.core.config import AgentConfig
from ai_agent.core.agent import AIVerificationAgent

config = AgentConfig()
config.target_coverage = 95.0
config.ml.algorithm = "ensemble"
config.enable_llm = False

agent = AIVerificationAgent(config)
summary = agent.run()
print(f"Coverage: {summary['final_coverage']:.2f}%")
```

### Custom ML Model
Extend `BaseLLMClient` or create a new ML optimizer:
```python
from ai_agent.ml.bayesian_opt import BayesianSeedOptimizer
from ai_agent.core.config import MLConfig

config = MLConfig()
config.bayesian_acquisition = "ucb"
config.bayesian_kappa = 3.0
optimizer = BayesianSeedOptimizer(config)

seed = optimizer.suggest_seed()
optimizer.update(seed, coverage_delta=5.0)
```

## Troubleshooting

### VCS Not Found
```
Error: VCS not found. Ensure Synopsys VCS is installed and in PATH.
```
**Fix**: Set `VCS_HOME` and add to `PATH`.

### LLM API Key Missing
```
Warning: OPENAI_API_KEY not set. LLM features will be disabled.
```
**Fix**: Export the appropriate API key environment variable.

### Compilation Errors
Check `sim_work/compile.log` for detailed VCS compilation output.

### No Coverage Improvement
- Increase `NUM_ITEMS` per simulation
- Switch to `ensemble` ML algorithm
- Enable LLM for strategic guidance
- Check if target coverage is achievable with the testbench constraints
