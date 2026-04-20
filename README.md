# ALU UVM Testbench with RL Verification Optimization

An 8-bit ALU with a SystemVerilog UVM testbench enhanced by **Reinforcement Learning** for stimulus generation optimization. The RL agent learns to generate targeted stimuli that achieve coverage closure significantly faster than constrained-random approaches.

## Overview

| Component | Description |
|-----------|-------------|
| **DUT** | 8-bit ALU: ADD, SUB, MUL, DIV, AND, XOR |
| **Testbench** | Full UVM 1.2 testbench (agent, driver, monitor, scoreboard, coverage) |
| **RL Engine** | Python-based RL using OpenAI Gymnasium + Stable-Baselines3 |
| **Bridge** | PyHDL-IF pattern bidirectional bridge (no DPI-C) |
| **Algorithms** | PPO, DQN, A2C (selectable via Makefile) |

## Repository Structure

```
ALU_Testbench_UVM_8Bit/
|-- DUT/                          # Design Under Test
|   |-- ALU_DUT.sv                # 8-bit ALU implementation
|   +-- ALU_interface.sv          # SV interface
|
|-- Testbench/                    # UVM Testbench
|   |-- ALU_pkg.sv                # Original package
|   |-- ALU_RL_pkg.sv             # RL-enhanced package
|   |-- ALU_Top.sv                # Original top module
|   |-- ALU_RL_Top.sv             # RL-enhanced top module
|   |-- ALU_Sequence_Item.sv      # Transaction class
|   |-- ALU_Sequence.sv           # Random sequences
|   |-- ALU_Sequencer.sv          # UVM sequencer
|   |-- ALU_Driver.sv             # Interface driver
|   |-- ALU_monitor.sv            # Output monitor
|   |-- ALU_Agent.sv              # UVM agent
|   |-- ALU_Env.sv                # UVM environment
|   |-- ALU_Scoreboard.sv         # Reference model checker
|   |-- ALU_Coverage_Collector.sv # Functional coverage
|   |-- Test.sv                   # Original test (80k random tx)
|   |-- bridge/
|   |   +-- pyhdl_if_bridge.sv    # SV side of Python bridge
|   |-- sequences/
|   |   +-- ALU_RL_Sequence.sv    # RL-guided sequences
|   +-- tests/
|       +-- ALU_RL_Test.sv        # RL test + Baseline test
|
|-- rl/                           # Python RL modules
|   |-- __init__.py
|   |-- alu_gym_env.py            # Gymnasium environment
|   |-- rl_agent.py               # SB3 agent wrapper
|   |-- bridge.py                 # Python bridge (PyHDL-IF pattern)
|   |-- train.py                  # Training entry point
|   |-- compare.py                # RL vs Random comparison
|   +-- run_rl_verification.py    # End-to-end runner
|
|-- scripts/                      # Shell scripts
|   |-- run_random.sh             # Run random simulation
|   |-- run_rl.sh                 # Run RL simulation
|   +-- compare.sh                # Run comparison
|
|-- docs/                         # Documentation
|   |-- architecture.md           # System architecture
|   +-- rl_methodology.md         # RL methodology details
|
|-- Makefile                      # Build & run system
|-- requirements.txt              # Python dependencies
+-- README.md                     # This file
```

## Quick Start

### Prerequisites
- **Synopsys VCS** (for HDL simulation)
- **Python 3.8+** with pip
- Linux environment

### 1. Install Python Dependencies
```bash
make install_deps
# or: pip3 install -r requirements.txt
```

### 2. Run RL vs Random Comparison (Python only, no VCS needed)
```bash
make compare RL_ALGO=PPO TRAIN_STEPS=50000
```

### 3. Train RL Agent
```bash
make train RL_ALGO=PPO TRAIN_STEPS=100000
```

### 4. Run VCS Simulations (requires VCS)
```bash
# Baseline random simulation
make sim NUM_TX=80000

# RL-guided simulation
make sim_rl RL_ALGO=PPO NUM_TX=1000

# Full flow: train + simulate both + compare
make all RL_ALGO=PPO
```

## Makefile Options

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_RL` | `0` | Enable RL stimulus |
| `RL_ALGO` | `PPO` | RL algorithm: PPO, DQN, A2C |
| `NUM_TX` | `1000` | Number of transactions |
| `TRAIN_STEPS` | `50000` | RL training timesteps |
| `SEED` | `42` | Random seed |
| `VERBOSITY` | `UVM_LOW` | UVM verbosity level |
| `GUI` | `0` | Launch DVE waveform viewer |
| `COV` | `1` | Enable functional coverage |
| `WAVES` | `0` | Dump waveforms to VPD |

## Architecture

```
+-------------------+          +------------------------+
|   Python RL       |  PyHDL   |   SystemVerilog UVM    |
|   (Gymnasium +    |  Bridge  |   (Sequences, Agent,   |
|    SB3 Agent)     |<-------->|    Scoreboard, Cov)    |
+-------------------+  (FIFO/  +------------------------+
                        File)            |
                                +--------+--------+
                                |   8-bit ALU DUT  |
                                +------------------+
```

The Python RL agent:
1. Observes current coverage state
2. Selects optimal stimulus (A, B, op_code, C_in)
3. Sends stimulus via PyHDL-IF bridge
4. Receives results and updated coverage
5. Computes reward (coverage improvement)
6. Updates policy to maximize future coverage gains

## Bridge Communication

Two modes of operation:

### File Mode (Batch, Recommended)
- Python generates all stimuli upfront, writes to file
- SV simulation reads stimuli from file
- No live connection needed during simulation

### Live Mode (Real-time)
- Named pipes (FIFOs) for bidirectional IPC
- Real-time stimulus/response exchange
- Handshake protocol with timeout handling

Protocol:
```
Python -> SV: STIMULUS <seq_id> <A> <B> <op_code> <C_in> <reset> <timestamp>
SV -> Python: RESPONSE <seq_id> <result> <C_out> <Z_flag> <coverage> ...
```

## Coverage Model

The ALU functional coverage includes:
- **A operand bins**: All_Ones (0xFF), All_Zeros (0x00), random
- **B operand bins**: All_Ones (0xFF), All_Zeros (0x00), random
- **Operation bins**: ADD, SUB, MUL, DIV, AND, XOR
- **Carry-in bins**: 0, 1
- **Cross-coverage**: All operations x corner cases (12 bins)

Total: 26 individual bins + 12 cross-coverage bins = 38 coverage points

## RL Algorithms

| Algorithm | Type | Best For |
|-----------|------|----------|
| **PPO** | On-policy, actor-critic | General purpose, stable training |
| **DQN** | Off-policy, value-based | Discrete actions, sample efficient |
| **A2C** | On-policy, actor-critic | Fast experiments, simple setups |

## Expected Results

The RL agent typically achieves 100% coverage in 30-80 transactions compared to 800-2000+ for constrained-random, representing a **10-25x improvement** in verification efficiency.

## UVM Testbench Structure

The original testbench follows standard UVM architecture:
- Agent contains Driver, Monitor, and Sequencer
- Environment connects Agent, Scoreboard, and Coverage Collector
- Monitor feeds transactions to both Scoreboard and Coverage via analysis ports

## Documentation

- [Architecture Details](docs/architecture.md)
- [RL Methodology](docs/rl_methodology.md)

## License

This project is for educational and research purposes.
