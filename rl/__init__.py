"""Python RL package for the 8-bit ALU UVM testbench.

Modules
-------
coverage_model : SystemVerilog-mirroring functional-coverage tracker.
alu_model      : Pure-Python reference model of the ALU (golden DUT).
alu_env        : Gymnasium env backed by ``alu_model`` (offline training).
bridge_env     : Gymnasium env backed by the PyHDL-IF 2-way bridge (online).
uvm_bridge     : PyHDL-IF @hdl_if.api class loaded by VCS at simulation time.
train          : stable-baselines3 training entry-point (PPO / DQN / A2C).
evaluate       : rollout + CSV/plot logging.
random_baseline: pure-random stimulus run for comparison.
compare        : produces the RL-vs-random comparison report.
"""
__all__ = [
    "coverage_model",
    "alu_model",
    "alu_env",
    "bridge_env",
    "uvm_bridge",
    "train",
    "evaluate",
    "random_baseline",
    "compare",
]
