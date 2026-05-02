# AId-VO User Guide

## Prerequisites

### Python Environment
- Python 3.9+
- pip or conda

### For VCS Simulation (optional)
- Synopsys VCS with UVM-1.2 support
- Valid VCS licence

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Verify installation
make py-smoke
```

## Quick Start

### 1. Smoke Test (No VCS Required)

```bash
make py-smoke
```

This verifies the entire Python RL stack is functional.

### 2. Train an RL Agent

```bash
# Train PPO (default)
make train

# Train specific algorithms
make train-ppo
make train-dqn
make train-a2c

# Custom parameters
make train AI_ALGORITHM=ppo AI_TIMESTEPS=100000 SEED=123
```

### 3. Evaluate Against Baseline

```bash
make evaluate AI_ALGORITHM=ppo
```

### 4. Full Comparison (PPO + DQN + A2C vs Baseline)

```bash
make compare
```

### 5. Generate Report

```bash
make report
```

## VCS Simulation

### Single Simulation Run

```bash
# Basic run
make sim SEED=42

# With coverage collection
make sim-coverage SEED=42
```

### AI-Directed VCS Verification

```bash
make sim-ai AI_ALGORITHM=ppo SIM_MODE=vcs
```

### Baseline VCS Verification

```bash
make sim-baseline SEED=42
```

## Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_ENABLED` | `1` | Enable AI (0=off, 1=on) |
| `AI_ALGORITHM` | `ppo` | RL algorithm: ppo, dqn, a2c |
| `AI_TIMESTEPS` | `50000` | Training timesteps |
| `AI_MAX_ITER` | `50` | Max verification iterations |
| `AI_TXN_PER_ITER` | `1000` | Transactions per iteration |
| `TARGET_COVERAGE` | `95.0` | Target coverage percentage |
| `SEED` | `42` | Random seed |
| `SIM_MODE` | `python` | Simulation mode: python or vcs |
| `NUM_ITEMS` | `5000` | VCS transaction count |
| `TEST` | `ALU_Test` | UVM test name |
| `VERBOSITY` | `UVM_LOW` | UVM verbosity level |
| `LEARNING_RATE` | `3e-4` | RL learning rate |
| `NUM_EVAL_EPISODES` | `10` | Evaluation episodes |
| `OUTPUT_DIR` | `results` | Output directory |

## Python API Usage

### Train and Evaluate Programmatically

```python
from ai.core.config import AIVerificationConfig
from ai.agents.coverage_agent import CoverageAgent

# Configure
config = AIVerificationConfig.from_args(
    algorithm="ppo",
    target_coverage=95.0,
    seed=42,
)

# Train
agent = CoverageAgent(
    algorithm="ppo",
    env_kwargs={"target_coverage": 95.0, "max_steps": 100},
)
summary = agent.train(total_timesteps=50000, save_path="models/ppo_model")

# Evaluate
results = agent.evaluate(n_episodes=10)
print(f"Mean coverage: {results['mean_coverage']:.1f}%")
```

### Use the Orchestrator

```python
from ai.core.config import AIVerificationConfig
from ai.core.orchestrator import Orchestrator

config = AIVerificationConfig.from_args(algorithm="ppo")
orch = Orchestrator(config)

# Run comparison
results = orch.run_comparison(algorithms=["ppo", "dqn", "a2c"])
```

### Analyse Coverage

```python
from ai.environments.alu_sim_model import CoverageModel, PythonSimRunner, StimulusGenerator

sim = PythonSimRunner()
gen = StimulusGenerator(seed=42)
txns = gen.generate_default(1000)
sim.run_batch(txns)

from ai.analysis.reporter import CoverageReporter
print(CoverageReporter.bin_status_table(sim.coverage))
print(CoverageReporter.gap_analysis(sim.coverage))
```

## Understanding the Output

### Coverage Trace
The comparison output includes a coverage trace showing how coverage evolves
over iterations for each algorithm. AI-directed approaches typically show:
- **Steeper initial climb**: AI quickly hits common bins
- **Faster plateau breaker**: AI targets corner cases when progress stalls
- **Fewer total transactions**: Same coverage with less simulation effort

### Comparison Metrics
- **Transaction Reduction**: % fewer transactions needed vs baseline
- **Iteration Reduction**: % fewer iterations needed
- **Speedup**: Wall-time ratio (baseline / AI)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: ai` | Run from project root, or `pip install -e .` |
| `No module named 'gymnasium'` | `pip install -r requirements.txt` |
| `VCS not found` | Use `SIM_MODE=python` (default) |
| Training is slow | Reduce `AI_TIMESTEPS`, or use `a2c` (fastest) |
| Low coverage | Increase `AI_MAX_ITER` and `AI_TXN_PER_ITER` |

## Creating a Distributable Archive

```bash
make zip
# Creates ../ALU_Testbench_UVM_8Bit_AIdVO.zip
```
