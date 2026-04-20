# Architecture: RL-Optimized ALU Verification

## System Overview

This project integrates Reinforcement Learning (RL) with a SystemVerilog UVM testbench for an 8-bit ALU to optimize stimulus generation and accelerate coverage closure.

```
+-------------------+          +------------------------+
|   Python RL       |          |   SystemVerilog UVM    |
|                   |          |                        |
|  +-------------+  |  PyHDL   |  +------------------+  |
|  | Gymnasium   |  |  Bridge  |  | UVM Testbench    |  |
|  | Environment |<----------->| (Sequences, etc.) |  |
|  +------+------+  |  (FIFO/  |  +--------+---------+  |
|         |         |   File)  |           |            |
|  +------+------+  |          |  +--------+---------+  |
|  |  SB3 Agent  |  |          |  |   8-bit ALU DUT  |  |
|  | (PPO/DQN/   |  |          |  +------------------+  |
|  |  A2C)       |  |          |                        |
|  +-------------+  |          +------------------------+
+-------------------+
```

## Component Details

### 1. DUT (Design Under Test)
- **ALU_DUT.sv**: 8-bit ALU with 6 operations (ADD, SUB, MUL, DIV, AND, XOR)
- **ALU_interface.sv**: SystemVerilog interface for signal connectivity

### 2. UVM Testbench (Original)
- **ALU_Sequence_Item**: Transaction with A[7:0], B[7:0], op_code[3:0], C_in, Reset
- **ALU_Sequence**: Base, reset, and test sequences (constrained random)
- **ALU_Sequencer**: Standard UVM sequencer
- **ALU_Driver**: Drives stimulus to DUT interface
- **ALU_monitor**: Captures DUT responses
- **ALU_Agent**: Contains driver, monitor, sequencer
- **ALU_Scoreboard**: Reference model comparison
- **ALU_Coverage_Collector**: Functional coverage with cross-coverage
- **ALU_Env**: Environment with agent, scoreboard, coverage
- **ALU_Test**: Original test with 80,000 random transactions

### 3. RL-Enhanced Components

#### Python Side (`rl/`)
| Module | Description |
|--------|-------------|
| `alu_gym_env.py` | Custom Gymnasium environment modeling ALU verification state |
| `rl_agent.py` | Stable-baselines3 agent wrapper (PPO, DQN, A2C) |
| `bridge.py` | PyHDL-IF bridge (named pipe + file modes) |
| `train.py` | Training entry point |
| `compare.py` | RL vs Random comparison framework |
| `run_rl_verification.py` | End-to-end verification runner |

#### SystemVerilog Side
| Module | Description |
|--------|-------------|
| `pyhdl_if_bridge.sv` | SV side of the 2-way bridge |
| `ALU_RL_Sequence.sv` | RL-guided sequence (reads from bridge) |
| `ALU_RL_Test.sv` | RL test + Baseline test classes |
| `ALU_RL_pkg.sv` | Extended package with RL components |
| `ALU_RL_Top.sv` | Top module for RL-enhanced testbench |

## Communication Bridge

### Protocol
```
Python (RL Agent)                    SystemVerilog (UVM)
     |                                      |
     |-- STIMULUS seq A B op cin rst ts --> |
     |                                      |
     |   (DUT processes transaction)        |
     |                                      |
     |<-- RESPONSE seq res cout zf cov -- --|
     |                                      |
     |   (RL computes reward, next action)  |
     |                                      |
     |-- STIMULUS seq A B op cin rst ts --> |
     |          ...                         |
     |-- DONE --------------------------->  |
```

### Two Operating Modes

1. **File Mode** (recommended for batch): Python writes all stimuli to a file, SV reads sequentially
2. **Live Mode** (real-time): Named pipes (FIFOs) for bidirectional real-time communication

### Handshake & Timeout
- Each message has a sequence ID for matching request/response
- Configurable timeout (default 30s) with automatic retry
- DONE message signals end of session
- ERROR messages propagated in both directions

## RL Environment Design

### Observation Space (28 dimensions)
- A bins (3): AllOnes hit, AllZeros hit, Random hit
- B bins (3): AllOnes hit, AllZeros hit, Random hit
- Op bins (6): One per ALU operation
- C_in bins (2): 0 and 1
- Cross bins (12): 6 ops x 2 corner cases
- Overall coverage percentage (1)
- Transaction ratio (1)

### Action Space (MultiDiscrete [5, 5, 6, 2])
- A category: 0x00, 0xFF, low-random, mid-random, high-random
- B category: 0x00, 0xFF, low-random, mid-random, high-random
- op_code: ADD(0), SUB(1), MUL(2), DIV(3), AND(4), XOR(5)
- C_in: 0 or 1

### Reward Function
- +10.0 per percentage point of new coverage
- +50.0 bonus for reaching 100% coverage
- -0.01 per transaction (efficiency penalty)
- +5.0 for reaching coverage milestones (25%, 50%, 75%, 90%, 95%)

## Build & Run Flow

```
make train          --> Train RL agent (offline, Python only)
make generate       --> Generate optimized stimulus file
make sim_rl         --> Compile + run VCS simulation with RL stimuli
make sim            --> Compile + run standard random simulation
make compare        --> Python-side comparison (no VCS needed)
make all            --> Full flow
```
