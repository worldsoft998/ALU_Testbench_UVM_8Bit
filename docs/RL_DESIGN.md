# RL Design

## MDP formulation

| Element | Choice |
|---------|--------|
| Agent      | stable-baselines3 (PPO, DQN, A2C) |
| Environment| `rl/alu_env.py` offline; `rl/bridge_env.py` online over the bridge |
| State      | full coverage hit-mask plus coverage % and episode progress |
| Action     | `MultiDiscrete([6, 256, 256, 2, 2])` = (op, A, B, C_in, Reset) |
| Reward     | `novelty_bonus * new_bins - redundancy_penalty` per step; `+5` on DUT mismatch |
| Episode end| coverage &ge; `target_coverage` **or** `max_steps` reached |

### Why `MultiDiscrete`?

The ALU's stimulus has mixed-type components; MultiDiscrete preserves the
natural factorisation, and PPO/A2C support it out of the box. DQN only
supports `Discrete`, so `rl.train._FlattenDiscreteActionWrapper` enumerates
the 6 &times; 16 &times; 16 &times; 2 &times; 2 = 6144-entry quantised
action space for DQN runs.

### Why a hit-mask as state?

A simple coverage-percentage scalar is too weakly-informative: two very
different hit distributions can map to the same %. Feeding the full
bin-hit bitmap lets the policy learn which specific *missing* bins it can
target next, which empirically accelerates closure considerably.

### Reward shaping

1. `+1.0` per new coverage bin hit (novelty).
2. `-0.01` per step that produces no new bin (redundancy penalty).
3. `+5.0` on scoreboard mismatch (online bridge only; encourages bug-finding).

## Observation space

| Slice        | Size | Meaning |
|--------------|------|---------|
| hit-mask     | 84   | binary hit indicator per bin |
| coverage %   | 1    | current coverage / 100 |
| step progress| 1    | step_idx / max_steps |

## Algorithm comparison (`make py-smoke` default run)

| Algo | max_steps | steps-to-100% | final coverage |
|------|-----------|---------------|----------------|
| PPO  | 2000      | ~164          | 100 %          |
| A2C  | 2000      | ~213          | 100 %          |
| DQN  | 2000      | ~350 (train 50k) | 100 %       |
| Random | 2000    | does not close | ~87 %         |

Results are machine- and seed-dependent. Rerun `make py-smoke` to refresh
`docs/results/compare.*`.

## Online vs offline training

1. **Offline** &mdash; default. Training drives `rl/alu_env.py`
   which talks to a pure-Python ALU reference model. Steps are ~5 &micro;s.
   50 k steps &asymp; 1 minute on a laptop.
2. **Online**  &mdash; `rl/bridge_env.py` pipes stimulus into a live
   VCS simulation and receives real RTL responses via the bridge.
   Useful for policy fine-tuning on the actual DUT.

## Extending to new DUTs

1. Describe the coverage bins in `rl/coverage_model.py` (mirror the SV
   covergroup). The env observation dimension is derived automatically.
2. Keep `rl/alu_model.py` as the Python golden model so offline training
   remains fast.
3. Expose new stimulus knobs in `MultiDiscrete` and the packing function
   in `rl/bridge_env.py::pack_request`.
4. Mirror the stimulus fields in `tb_rl/bridge/alu_rl_bridge.sv`.
