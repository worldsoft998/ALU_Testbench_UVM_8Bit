# RL Methodology for Hardware Verification

## Problem Formulation

Hardware verification aims to ensure a design (DUT) behaves correctly across all input combinations. The challenge is that exhaustive testing is infeasible -- for an 8-bit ALU with 2 operands, carry-in, and 6 operations, there are 2^8 * 2^8 * 6 * 2 = 786,432 unique input combinations.

Traditional constrained-random verification relies on randomized stimuli with constraints. While effective, it wastes cycles on already-covered regions of the input space and may take a long time to hit rare corner cases.

## RL-Based Approach

We model the verification task as a Markov Decision Process (MDP):

- **State**: Current coverage status (which bins are hit/missed)
- **Action**: Next stimulus to apply (operand values, operation, carry)
- **Reward**: Coverage improvement from the stimulus
- **Terminal**: All coverage bins hit, or maximum transactions reached

The RL agent learns a policy that maps coverage state to stimulus selection, maximizing cumulative coverage improvement while minimizing the number of transactions needed.

## Why RL Works for Verification

1. **Sequential Decision Making**: Each stimulus choice affects what coverage gaps remain, making it a sequential problem well-suited for RL.

2. **Sparse Reward Signal**: Later coverage bins become progressively harder to hit. RL excels at learning strategies for delayed/sparse rewards.

3. **Generalization**: A trained agent can transfer knowledge across similar designs or constraint scenarios.

4. **Adaptivity**: Unlike static constrained-random, RL adapts its strategy based on current coverage state.

## Algorithms Used

### PPO (Proximal Policy Optimization)
- **Type**: On-policy, actor-critic
- **Strengths**: Stable training, good sample efficiency, works with discrete and continuous actions
- **Best for**: General-purpose verification optimization
- **Key params**: clip_range=0.2, learning_rate=3e-4, n_steps=256

### DQN (Deep Q-Network)
- **Type**: Off-policy, value-based
- **Strengths**: Sample-efficient via replay buffer, good for discrete actions
- **Best for**: ALU verification (naturally discrete action space)
- **Key params**: buffer_size=50000, exploration_fraction=0.3, target_update=500

### A2C (Advantage Actor-Critic)
- **Type**: On-policy, actor-critic
- **Strengths**: Simple, fast training, synchronous updates
- **Best for**: Quick experiments, smaller action spaces
- **Key params**: n_steps=5, learning_rate=7e-4

## Training Process

```
1. Initialize Gymnasium environment with ALU coverage model
2. Create SB3 agent with chosen algorithm
3. For each training step:
   a. Agent observes coverage state
   b. Agent selects action (stimulus parameters)
   c. Environment simulates ALU + updates coverage
   d. Environment computes reward (coverage improvement)
   e. Agent updates policy based on reward
4. Save trained model
5. Generate optimized stimuli using greedy policy
```

## Offline vs Online Mode

### Offline (Recommended)
- Train agent using Python-side ALU model (no VCS needed)
- Generate stimulus file
- Run VCS simulation with pre-generated stimuli
- Fast iteration, reproducible results

### Online (Live)
- Agent connected to VCS via named pipes
- Real-time stimulus generation based on actual SV coverage
- More accurate but requires VCS license during training
- Uses PyHDL-IF bridge pattern (no DPI-C)

## Expected Results

Based on the ALU coverage model (26 individual bins + 12 cross-coverage bins):

| Metric | Random | RL (PPO) | Improvement |
|--------|--------|----------|-------------|
| Transactions to 100% | ~800-2000 | ~30-80 | 10-25x |
| Coverage at 100 tx | ~70-80% | ~95-100% | +15-25% |
| Corner case hit rate | Low (random) | High (targeted) | Significant |

The RL agent learns to:
1. Systematically cover all 6 operations early
2. Target corner cases (0x00, 0xFF) for both operands
3. Exercise both carry-in values
4. Hit cross-coverage bins (corner cases x operations) efficiently

## Limitations and Considerations

1. **Training overhead**: Initial training takes time (offset by faster simulations)
2. **Coverage model fidelity**: Offline mode uses a Python approximation of SV coverage
3. **Scalability**: More complex DUTs need larger observation/action spaces
4. **Generalization**: Model may need retraining if coverage goals change
