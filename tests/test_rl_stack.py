#!/usr/bin/env python3
"""
Unit tests for the AId-VO RL verification stack.

Run:  python tests/test_rl_stack.py
      python -m pytest tests/test_rl_stack.py -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.environments.alu_sim_model import (
    ALUModel,
    ALUTransaction,
    CoverageModel,
    PythonSimRunner,
    StimulusGenerator,
)
from ai.environments.alu_coverage_env import ALUCoverageEnv
from ai.generators.seed_optimizer import SeedOptimizer
from ai.generators.stimulus_generator import AIDirectedStimulusEngine, SimulationDirective
from ai.parsers.coverage_parser import UnifiedCoverageParser
from ai.core.config import AIVerificationConfig, RLConfig, CoverageConfig
from ai.analysis.comparator import VerificationComparator


class TestALUModel(unittest.TestCase):
    """Verify the Python ALU model matches the DUT specification."""

    def setUp(self):
        self.alu = ALUModel()

    def test_add(self):
        txn = self.alu.execute(10, 20, 0, 0)
        self.assertEqual(txn.result, 30)
        self.assertEqual(txn.c_out, 0)
        self.assertEqual(txn.z_flag, 0)

    def test_add_carry(self):
        txn = self.alu.execute(0xFF, 1, 0, 0)
        self.assertEqual(txn.result, 256)
        self.assertEqual(txn.c_out, 1)

    def test_add_with_carry_in(self):
        txn = self.alu.execute(5, 3, 0, 1)
        self.assertEqual(txn.result, 9)

    def test_sub(self):
        txn = self.alu.execute(30, 10, 1, 0)
        self.assertEqual(txn.result, 20)
        self.assertEqual(txn.c_out, 0)

    def test_sub_underflow(self):
        txn = self.alu.execute(10, 20, 1, 0)
        result_16bit = (10 - 20) & 0xFFFF
        self.assertEqual(txn.result, result_16bit)
        self.assertEqual(txn.c_out, 1)

    def test_mult(self):
        txn = self.alu.execute(15, 15, 2, 0)
        self.assertEqual(txn.result, 225)
        self.assertEqual(txn.c_out, 0)

    def test_mult_large(self):
        txn = self.alu.execute(0xFF, 0xFF, 2, 0)
        self.assertEqual(txn.result, 0xFE01)

    def test_div(self):
        txn = self.alu.execute(100, 10, 3, 0)
        self.assertEqual(txn.result, 10)

    def test_div_by_zero(self):
        txn = self.alu.execute(100, 0, 3, 0)
        self.assertEqual(txn.result, 0)

    def test_and(self):
        txn = self.alu.execute(0xAA, 0x55, 4, 0)
        self.assertEqual(txn.result, 0)
        self.assertEqual(txn.z_flag, 1)

    def test_xor(self):
        txn = self.alu.execute(0xFF, 0xFF, 5, 0)
        self.assertEqual(txn.result, 0)
        self.assertEqual(txn.z_flag, 1)

    def test_z_flag_set(self):
        txn = self.alu.execute(5, 5, 1, 0)
        self.assertEqual(txn.result, 0)
        self.assertEqual(txn.z_flag, 1)

    def test_z_flag_clear(self):
        txn = self.alu.execute(5, 3, 0, 0)
        self.assertNotEqual(txn.result, 0)
        self.assertEqual(txn.z_flag, 0)


class TestCoverageModel(unittest.TestCase):
    """Verify coverage bin tracking matches the UVM covergroup."""

    def setUp(self):
        self.cov = CoverageModel()

    def test_initial_state(self):
        self.assertEqual(self.cov.total_covered, 0)
        self.assertEqual(self.cov.coverage_percentage, 0.0)
        self.assertEqual(len(self.cov.BIN_NAMES), 28)

    def test_a_all_ones(self):
        self.cov.sample(ALUTransaction(a=0xFF, b=0x00, opcode=0))
        self.assertIn("A_All_Ones", [n for n, c in zip(self.cov.BIN_NAMES, self.cov.hit_count) if c > 0])

    def test_corner_case_cross(self):
        self.cov.sample(ALUTransaction(a=0xFF, b=0xFF, opcode=0))
        self.assertGreater(self.cov.hit_count[16], 0)  # Add_cross1

    def test_full_coverage(self):
        for op in range(6):
            self.cov.sample(ALUTransaction(a=0xFF, b=0xFF, opcode=op, c_in=0, reset=0))
            self.cov.sample(ALUTransaction(a=0x00, b=0x00, opcode=op, c_in=1, reset=1))
            self.cov.sample(ALUTransaction(a=0x42, b=0x42, opcode=op))
        self.assertEqual(self.cov.coverage_percentage, 100.0)

    def test_reset(self):
        self.cov.sample(ALUTransaction(a=0xFF, b=0xFF, opcode=0))
        self.assertGreater(self.cov.total_covered, 0)
        self.cov.reset()
        self.assertEqual(self.cov.total_covered, 0)

    def test_state_vector_shape(self):
        vec = self.cov.get_state_vector()
        self.assertEqual(vec.shape[0], 29)  # 28 bins + 1 overall


class TestStimulusGenerator(unittest.TestCase):
    """Verify stimulus generation."""

    def test_default_generation(self):
        gen = StimulusGenerator(seed=42)
        txns = gen.generate_default(100)
        self.assertEqual(len(txns), 100)
        opcodes = {t.opcode for t in txns}
        self.assertTrue(len(opcodes) > 1)

    def test_biased_generation(self):
        gen = StimulusGenerator(seed=42)
        weights = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]  # only XOR
        txns = gen.generate_biased(100, opcode_weights=weights)
        xor_count = sum(1 for t in txns if t.opcode == 5)
        self.assertGreater(xor_count, 80)

    def test_seed_determinism(self):
        gen1 = StimulusGenerator(seed=123)
        gen2 = StimulusGenerator(seed=123)
        txns1 = gen1.generate_default(50)
        txns2 = gen2.generate_default(50)
        for t1, t2 in zip(txns1, txns2):
            self.assertEqual(t1.a, t2.a)
            self.assertEqual(t1.b, t2.b)
            self.assertEqual(t1.opcode, t2.opcode)


class TestPythonSimRunner(unittest.TestCase):
    """Verify the Python simulation runner."""

    def test_basic_run(self):
        sim = PythonSimRunner()
        gen = StimulusGenerator(seed=42)
        txns = gen.generate_default(500)
        cov = sim.run_batch(txns)
        self.assertGreater(cov, 0.0)
        self.assertEqual(sim.total_transactions, 500)

    def test_coverage_accumulates(self):
        sim = PythonSimRunner()
        gen = StimulusGenerator(seed=42)
        cov1 = sim.run_batch(gen.generate_default(100))
        cov2 = sim.run_batch(gen.generate_default(100))
        self.assertGreaterEqual(cov2, cov1)
        self.assertEqual(sim.total_transactions, 200)


class TestALUCoverageEnv(unittest.TestCase):
    """Verify the Gymnasium environment."""

    def test_env_creation(self):
        env = ALUCoverageEnv(target_coverage=95.0, max_steps=10)
        self.assertIsNotNone(env.observation_space)
        self.assertIsNotNone(env.action_space)

    def test_reset(self):
        env = ALUCoverageEnv(max_steps=10)
        obs, info = env.reset(seed=42)
        self.assertEqual(obs.shape[0], CoverageModel.NUM_BINS + 2)

    def test_step(self):
        env = ALUCoverageEnv(max_steps=10)
        obs, _ = env.reset(seed=42)
        action = env.action_space.sample()
        obs2, reward, terminated, truncated, info = env.step(action)
        self.assertEqual(obs2.shape, obs.shape)
        self.assertIn("coverage_pct", info)

    def test_episode(self):
        env = ALUCoverageEnv(max_steps=5, target_coverage=50.0)
        obs, _ = env.reset(seed=42)
        total_reward = 0
        for _ in range(5):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            if terminated or truncated:
                break
        self.assertGreater(info["coverage_pct"], 0)


class TestSeedOptimizer(unittest.TestCase):
    """Verify seed optimisation logic."""

    def test_suggest_seeds(self):
        opt = SeedOptimizer(base_seed=42)
        cov = CoverageModel()
        seeds = opt.suggest_seeds(5, cov)
        self.assertEqual(len(seeds), 5)
        self.assertEqual(len(set(seeds)), 5)

    def test_opcode_weights(self):
        opt = SeedOptimizer()
        cov = CoverageModel()
        weights = opt.suggest_opcode_weights(cov)
        self.assertEqual(len(weights), 6)
        self.assertAlmostEqual(sum(weights), 1.0, places=5)


class TestConfig(unittest.TestCase):
    """Verify configuration management."""

    def test_default_config(self):
        cfg = AIVerificationConfig()
        self.assertEqual(cfg.rl.algorithm, "ppo")
        self.assertEqual(cfg.coverage.num_bins, 28)

    def test_from_args(self):
        cfg = AIVerificationConfig.from_args(algorithm="dqn", seed=99)
        self.assertEqual(cfg.rl.algorithm, "dqn")
        self.assertEqual(cfg.rl.seed, 99)

    def test_save_load(self, tmp_path="/tmp/test_aidvo_config.json"):
        cfg = AIVerificationConfig.from_args(algorithm="a2c")
        cfg.save(tmp_path)
        loaded = AIVerificationConfig.load(tmp_path)
        self.assertEqual(loaded.rl.algorithm, "a2c")
        Path(tmp_path).unlink(missing_ok=True)


class TestComparator(unittest.TestCase):
    """Verify comparison logic."""

    def test_comparison_metrics(self):
        comp = VerificationComparator()
        ai_data = {
            "name": "ppo",
            "final_coverage": 95.0,
            "total_transactions": 5000,
            "iterations": 10,
            "total_wall_time": 2.0,
        }
        bl_data = {
            "name": "baseline",
            "final_coverage": 80.0,
            "total_transactions": 10000,
            "iterations": 50,
            "total_wall_time": 5.0,
        }
        metrics = comp.compare(ai_data, bl_data)
        self.assertEqual(metrics.coverage_improvement, 15.0)
        self.assertAlmostEqual(metrics.transaction_reduction_pct, 50.0)


class TestDirective(unittest.TestCase):
    """Verify simulation directive generation."""

    def test_vcs_plusargs(self):
        d = SimulationDirective(seed=12345, num_transactions=1000)
        args = d.to_vcs_plusargs()
        # +ntb_random_seed is NOT in plusargs (handled by run_vcs.sh --seed)
        self.assertFalse(any("ntb_random_seed" in a for a in args))
        self.assertTrue(any("AI_OPERAND_BIAS" in a for a in args))

    def test_engine_baseline(self):
        engine = AIDirectedStimulusEngine(base_seed=42)
        d = engine.create_baseline_directive(seed=100, num_transactions=500)
        self.assertEqual(d.seed, 100)
        self.assertEqual(d.num_transactions, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
