# ALU Verification with Reinforcement Learning - Architecture

## System Overview

The ALU verification system consists of three main components:

1. **Hardware Verification Environment** (SystemVerilog UVM)
2. **RL Agent Environment** (Python Gymnasium)
3. **Communication Bridge** (PyHDL-IF TCP/IP)

## Block Diagram

```
+-------------------+     TCP/IP      +-------------------+     RL Env     +-------------------+
|   UVM Testbench   |<--------------->|  PyHDL-IF Bridge  |<------------>|   RL Environment  |
|   (SystemVerilog) |                 |     (Python)      |              |   (Gymnasium)     |
+-------------------+                 +-------------------+              +-------------------+
        |                                       |                                |
        v                                       v                                v
+-------------------+                 +-------------------+              +-------------------+
|   DUT (ALU)       |                 |  Message Queue    |              |   RL Agent        |
|   8-bit ALU       |                 |  - Stimulus Req   |              |   - PPO/A2C/DQN   |
+-------------------+                 |  - Coverage Data  |              |   - Reward Calc   |
        ^                               |  - Reward Signal |              |   - Action Gen    |
        |                               +-------------------+              +-------------------+
        |                                                                              ^
        |                                                                              |
+-------------------+                                                              |
|   Coverage        |---------------------------------------------------------------+
|   Collector       |                                              Action
+-------------------+                                              Feedback
```

## Component Details

### 1. UVM Testbench Components

#### Agent
- Contains Driver, Monitor, Sequencer
- Orchestrates stimulus generation and response collection
- Connects to RL bridge when AI mode enabled

#### Driver
- Applies stimuli to DUT interface
- Two modes: Standard (random) and AI-assisted
- Tracks statistics on stimulus generation source

#### Monitor
- Samples DUT inputs and outputs
- Forwards transactions to scoreboard and coverage collector
- Provides data for RL feedback

#### Scoreboard
- Compares expected vs actual results
- Tracks bug detection statistics
- Reports error categorization for analysis

#### Coverage Collector
- Functional coverage tracking
- Op-code coverage
- Corner case coverage
- Exports data for RL decision making

### 2. PyHDL-IF Bridge

The bridge provides bidirectional communication:

#### Message Types
- `STIMULUS`: Request AI-generated stimulus
- `RESPONSE`: DUT response data
- `COVERAGE`: Coverage state update
- `REWARD`: RL reward signal
- `ACTION`: Action request/response
- `TERMINATE`: End simulation
- `HEARTBEAT`: Keep-alive

#### Handshake Protocol
1. Python sends `ACTION` or `STIMULUS` request
2. UVM receives and processes
3. UVM sends `RESPONSE` or `COVERAGE`
4. Python updates RL environment
5. Python sends `REWARD` signal

#### Timeout Handling
- Configurable timeout per message
- Automatic retry on timeout
- Status reporting for debugging

### 3. RL Environment

#### State Space (17 dimensions)
- Coverage vector: 12 elements
- Transaction count: normalized
- Bug count: normalized
- Last op_code: normalized
- Last A, B: normalized

#### Action Space (MultiDiscrete)
- op_code: 6 values (ADD, SUB, MULT, DIV, AND, XOR)
- A: 256 values (0-255)
- B: 256 values (0-255)
- C_in: 2 values (0, 1)

#### Reward Function
```
reward = coverage_increase * 100
       + exploration_bonus (0.1 for new states)
       + corner_case_bonus (0.5 for edge cases)
       - time_penalty (0.01)
```

## Data Flow

### Baseline (No AI) Mode
```
1. Sequence generates random stimulus
2. Driver applies to DUT
3. Monitor captures response
4. Scoreboard compares
5. Coverage collector samples
```

### AI-Assisted Mode
```
1. UVM requests action from bridge
2. Bridge sends to Python RL server
3. RL agent selects action based on state
4. Python returns optimized stimulus
5. Driver applies to DUT
6. Monitor captures response
7. Scoreboard compares
8. Coverage collector samples
9. Coverage data sent to Python
10. RL agent receives reward and updates
```

## File Organization

```
ALU_Testbench_UVM_8Bit/
├── DUT/
│   ├── ALU_DUT.sv           # RTL implementation
│   └── ALU_interface.sv     # Interface definition
│
├── Testbench/
│   ├── ALU_pkg.sv           # Standard UVM package
│   ├── ALU_RL_pkg.sv        # RL-enhanced package
│   ├── ALU_Sequence_Item.sv # Transaction item
│   ├── ALU_Sequence.sv      # Base sequences
│   ├── ALU_RL_Sequence.sv   # RL-aware sequences
│   ├── ALU_Sequencer.sv     # Sequencer
│   ├── ALU_Driver.sv        # Driver
│   ├── ALU_RL_Driver.sv     # RL driver
│   ├── ALU_monitor.sv       # Monitor
│   ├── ALU_Agent.sv         # Agent
│   ├── ALU_RL_Agent.sv      # RL agent
│   ├── ALU_Env.sv           # Environment
│   ├── ALU_RL_Env.sv       # RL environment
│   ├── ALU_Coverage_Collector.sv     # Coverage
│   ├── ALU_RL_Coverage_Collector.sv # RL coverage
│   ├── ALU_Scoreboard.sv    # Scoreboard
│   ├── ALU_RL_Scoreboard.sv # RL scoreboard
│   ├── ALU_RL_Bridge.sv     # Bridge component
│   ├── Test.sv              # Base test
│   ├── ALU_RL_Test.sv      # RL test
│   └── ALU_Top.sv           # Testbench top
│
├── Python/
│   ├── RL/
│   │   ├── alu_rl_environment.py  # Gymnasium env
│   │   ├── rl_agents.py            # Agent implementations
│   │   └── rl_trainer.py           # Training interface
│   ├── Bridge/
│   │   └── pyhdl_if_bridge.py     # TCP/IP bridge
│   ├── Analysis/
│   │   └── comparison_report.py   # Result analysis
│   ├── start_rl_server.py         # RL server
│   └── train_agent.py             # Training script
│
└── Scripts/
    └── run_simulation.sh           # Simulation runner
```

## Configuration Options

### Simulation Configuration
- `USE_AI`: Enable/disable AI assistance
- `ALGORITHM`: RL algorithm (ppo, a2c, dqn, sac, td3, random)
- `NUM_TRANSACTIONS`: Number of transactions to run
- `COVERAGE_TARGET`: Target coverage percentage
- `PYTHON_HOST`: RL server host
- `PYTHON_PORT`: RL server port

### RL Configuration
- `learning_rate`: Agent learning rate
- `gamma`: Discount factor
- `n_steps`: Number of steps per update
- `batch_size`: Batch size for training
- `total_timesteps`: Total training steps

## Performance Metrics

### Coverage Efficiency
- Transactions per 1% coverage
- Time to reach coverage target
- Unique states visited

### Bug Detection
- Bugs found per transaction
- Corner case coverage
- Edge case discovery rate