"""
ALU Verification Gymnasium Environment
========================================
Custom OpenAI Gymnasium environment for RL-driven ALU verification.

Observation space: Current coverage state vector
Action space: ALU stimulus parameters (A, B, op_code, C_in)
Reward: Coverage improvement per transaction (encourages coverage closure)
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import logging
from typing import Optional, Dict, Any, Tuple

from .bridge import PyHDLBridge, FileBridge, ResponseMessage, CoverageReport

logger = logging.getLogger(__name__)


# ALU operation names for readability
ALU_OPS = {0: "ADD", 1: "SUB", 2: "MUL", 3: "DIV", 4: "AND", 5: "XOR"}
NUM_OPS = len(ALU_OPS)

# Coverage bin definitions matching the SV covergroup
NUM_A_BINS = 3      # All_Ones, All_Zeros, random_stimulus
NUM_B_BINS = 3      # All_Ones, All_Zeros, random_stimulus
NUM_OP_BINS = 6     # add, sub, mul, div, and, xor
NUM_CIN_BINS = 2    # 0, 1
NUM_CROSS_BINS = 12 # 6 ops x 2 corner cases (AllOnes+AllOnes, AllZeros+AllZeros)

# Total coverage bins tracked
TOTAL_BINS = NUM_A_BINS + NUM_B_BINS + NUM_OP_BINS + NUM_CIN_BINS + NUM_CROSS_BINS


class ALUVerifEnv(gym.Env):
    """
    Gymnasium environment for ALU verification optimization.

    The RL agent selects stimulus values (A, B, op_code, C_in) and
    receives rewards based on how much new coverage each transaction achieves.

    Observation:
        A vector of coverage bin hit/miss states plus the current overall
        coverage percentage and transaction count ratio.

    Action:
        MultiDiscrete: [A_category(3), B_category(3), op_code(6), C_in(2)]
        where A/B categories are: 0=0x00, 1=0xFF, 2=random

    Reward:
        +10.0 for each new coverage bin hit
        +50.0 bonus for reaching 100% coverage
        -0.01 per transaction (encourages efficiency)
        +1.0 for new cross-coverage bin hit
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(
        self,
        bridge: Optional[PyHDLBridge] = None,
        max_transactions: int = 5000,
        target_coverage: float = 100.0,
        render_mode: Optional[str] = None,
        offline_mode: bool = True,
    ):
        """
        Initialize the ALU verification environment.

        Args:
            bridge: PyHDL-IF bridge instance for SV communication.
            max_transactions: Maximum transactions per episode.
            target_coverage: Target coverage percentage to reach.
            render_mode: Gymnasium render mode.
            offline_mode: If True, simulate coverage locally without SV.
        """
        super().__init__()

        self.bridge = bridge
        self.max_transactions = max_transactions
        self.target_coverage = target_coverage
        self.render_mode = render_mode
        self.offline_mode = offline_mode

        # Action space: [A_category, B_category, op_code, C_in]
        # A_category/B_category: 0=0x00, 1=0xFF, 2=random(low), 3=random(mid), 4=random(high)
        self.action_space = spaces.MultiDiscrete([5, 5, NUM_OPS, 2])

        # Observation space: coverage bin states + metadata
        # [a_bins(3), b_bins(3), op_bins(6), cin_bins(2), cross_bins(12),
        #  overall_coverage(1), transaction_ratio(1)]
        obs_size = TOTAL_BINS + 2
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )

        # Internal state
        self._coverage_bins = np.zeros(TOTAL_BINS, dtype=np.float32)
        self._prev_coverage = 0.0
        self._transaction_count = 0
        self._episode_reward = 0.0
        self._episode_count = 0

        # Coverage tracking arrays (matching SV covergroup structure)
        self._a_bins = np.zeros(NUM_A_BINS, dtype=np.float32)  # AllOnes, AllZeros, random
        self._b_bins = np.zeros(NUM_B_BINS, dtype=np.float32)
        self._op_bins = np.zeros(NUM_OP_BINS, dtype=np.float32)
        self._cin_bins = np.zeros(NUM_CIN_BINS, dtype=np.float32)
        self._cross_bins = np.zeros(NUM_CROSS_BINS, dtype=np.float32)

        # Statistics
        self._stats = {
            'episodes': 0,
            'total_transactions': 0,
            'best_coverage': 0.0,
            'avg_transactions_to_close': [],
            'coverage_trajectory': [],
        }

        # Stimulus generation log (for file-mode batch writing)
        self._stimulus_log = []

        logger.info(
            f"ALUVerifEnv initialized: max_tx={max_transactions}, "
            f"target={target_coverage}%, offline={offline_mode}"
        )

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict] = None
    ) -> Tuple[np.ndarray, Dict]:
        """Reset environment for a new episode."""
        super().reset(seed=seed)

        self._coverage_bins = np.zeros(TOTAL_BINS, dtype=np.float32)
        self._a_bins = np.zeros(NUM_A_BINS, dtype=np.float32)
        self._b_bins = np.zeros(NUM_B_BINS, dtype=np.float32)
        self._op_bins = np.zeros(NUM_OP_BINS, dtype=np.float32)
        self._cin_bins = np.zeros(NUM_CIN_BINS, dtype=np.float32)
        self._cross_bins = np.zeros(NUM_CROSS_BINS, dtype=np.float32)
        self._prev_coverage = 0.0
        self._transaction_count = 0
        self._episode_reward = 0.0
        self._stimulus_log = []

        self._episode_count += 1
        self._stats['episodes'] = self._episode_count

        obs = self._get_observation()
        info = {'coverage': 0.0, 'transaction_count': 0}

        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one verification step.

        Args:
            action: [A_category, B_category, op_code, C_in]

        Returns:
            observation, reward, terminated, truncated, info
        """
        a_cat, b_cat, op_code, c_in = action

        # Convert action categories to actual stimulus values
        A = self._category_to_value(int(a_cat))
        B = self._category_to_value(int(b_cat))
        op_code = int(op_code)
        c_in = int(c_in)

        self._transaction_count += 1
        self._stats['total_transactions'] += 1

        # Log stimulus for batch mode
        self._stimulus_log.append({
            'A': A, 'B': B, 'op_code': op_code,
            'C_in': c_in, 'reset': 0
        })

        if self.offline_mode:
            # Simulate ALU and coverage locally
            result, c_out, z_flag = self._simulate_alu(A, B, op_code, c_in)
            self._update_coverage_model(A, B, op_code, c_in)
        else:
            # Use bridge to communicate with SV simulation
            resp = self.bridge.send_and_receive(A, B, op_code, c_in, reset=0)
            self._update_coverage_from_response(resp)

        # Calculate reward
        current_coverage = self._calculate_coverage()
        coverage_delta = current_coverage - self._prev_coverage
        reward = self._calculate_reward(coverage_delta, current_coverage)
        self._prev_coverage = current_coverage
        self._episode_reward += reward

        # Track stats
        self._stats['best_coverage'] = max(
            self._stats['best_coverage'], current_coverage
        )
        self._stats['coverage_trajectory'].append(current_coverage)

        # Termination conditions
        terminated = current_coverage >= self.target_coverage
        truncated = self._transaction_count >= self.max_transactions

        if terminated:
            self._stats['avg_transactions_to_close'].append(self._transaction_count)

        obs = self._get_observation()
        info = {
            'coverage': current_coverage,
            'coverage_delta': coverage_delta,
            'transaction_count': self._transaction_count,
            'episode_reward': self._episode_reward,
            'stimulus': {'A': A, 'B': B, 'op_code': ALU_OPS.get(op_code, '?'),
                         'C_in': c_in},
        }

        return obs, reward, terminated, truncated, info

    def _category_to_value(self, category: int) -> int:
        """Convert an action category to an 8-bit value."""
        if category == 0:
            return 0x00
        elif category == 1:
            return 0xFF
        elif category == 2:
            return self.np_random.integers(0x01, 0x55)
        elif category == 3:
            return self.np_random.integers(0x55, 0xAA)
        elif category == 4:
            return self.np_random.integers(0xAA, 0xFF)
        return self.np_random.integers(0, 256)

    def _simulate_alu(self, A: int, B: int, op_code: int,
                      C_in: int) -> Tuple[int, int, int]:
        """
        Local ALU simulation (matches DUT behavior).
        Used in offline mode for training without SV simulation.
        """
        A = A & 0xFF
        B = B & 0xFF

        if op_code == 0:    # ADD
            result = A + B + C_in
            c_out = (result >> 8) & 1
        elif op_code == 1:  # SUB
            result = A - B
            c_out = (result >> 8) & 1
            result = result & 0xFFFF
        elif op_code == 2:  # MUL
            result = A * B
            c_out = 0
        elif op_code == 3:  # DIV
            result = A // B if B != 0 else 0
            c_out = 0
        elif op_code == 4:  # AND
            result = A & B
            c_out = 0
        elif op_code == 5:  # XOR
            result = A ^ B
            c_out = 0
        else:
            result = 0
            c_out = 0

        result = result & 0xFFFF
        z_flag = 1 if result == 0 else 0

        return result, c_out, z_flag

    def _update_coverage_model(self, A: int, B: int, op_code: int, C_in: int):
        """Update local coverage model based on stimulus."""
        # A bins: AllOnes(0), AllZeros(1), random(2)
        if A == 0xFF:
            self._a_bins[0] = 1.0
        elif A == 0x00:
            self._a_bins[1] = 1.0
        else:
            self._a_bins[2] = 1.0

        # B bins
        if B == 0xFF:
            self._b_bins[0] = 1.0
        elif B == 0x00:
            self._b_bins[1] = 1.0
        else:
            self._b_bins[2] = 1.0

        # Op bins
        if 0 <= op_code < NUM_OP_BINS:
            self._op_bins[op_code] = 1.0

        # C_in bins
        self._cin_bins[C_in & 1] = 1.0

        # Cross coverage bins (corner cases)
        # Index: op_code * 2 + case_index
        # case_index: 0 = AllOnes x AllOnes, 1 = AllZeros x AllZeros
        if A == 0xFF and B == 0xFF and 0 <= op_code < NUM_OPS:
            self._cross_bins[op_code * 2] = 1.0
        if A == 0x00 and B == 0x00 and 0 <= op_code < NUM_OPS:
            self._cross_bins[op_code * 2 + 1] = 1.0

        # Rebuild flat coverage vector
        self._coverage_bins = np.concatenate([
            self._a_bins, self._b_bins, self._op_bins,
            self._cin_bins, self._cross_bins
        ])

    def _update_coverage_from_response(self, resp: ResponseMessage):
        """Update coverage from SV bridge response."""
        # The SV side sends overall coverage; we track it
        self._prev_coverage = resp.coverage_pct

    def _calculate_coverage(self) -> float:
        """Calculate overall coverage percentage."""
        if self.offline_mode:
            total_bins = len(self._coverage_bins)
            hit_bins = np.sum(self._coverage_bins > 0)
            return (hit_bins / total_bins) * 100.0 if total_bins > 0 else 0.0
        return self._prev_coverage

    def _calculate_reward(self, coverage_delta: float,
                          current_coverage: float) -> float:
        """
        Calculate reward for the RL agent.

        Reward structure:
            - +10.0 per percentage point of new coverage
            - +50.0 bonus for reaching target coverage
            - -0.01 per transaction (time penalty)
            - Additional bonus for cross-coverage hits
        """
        reward = 0.0

        # Coverage improvement reward
        if coverage_delta > 0:
            reward += coverage_delta * 10.0

        # Small penalty per transaction (encourage efficiency)
        reward -= 0.01

        # Bonus for reaching target
        if current_coverage >= self.target_coverage:
            reward += 50.0

        # Bonus for high coverage milestones
        milestones = [25.0, 50.0, 75.0, 90.0, 95.0]
        for m in milestones:
            if (current_coverage >= m and
                    (current_coverage - coverage_delta) < m):
                reward += 5.0

        return reward

    def _get_observation(self) -> np.ndarray:
        """Construct observation vector."""
        coverage_pct = self._calculate_coverage() / 100.0
        tx_ratio = self._transaction_count / self.max_transactions

        obs = np.concatenate([
            self._coverage_bins,
            np.array([coverage_pct, tx_ratio], dtype=np.float32)
        ])

        return obs.astype(np.float32)

    def get_stimulus_log(self) -> list:
        """Return all stimuli generated in the current episode."""
        return self._stimulus_log.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Return environment statistics."""
        return self._stats.copy()

    def render(self):
        """Render environment state."""
        if self.render_mode == "human":
            cov = self._calculate_coverage()
            print(f"[Tx {self._transaction_count:5d}] Coverage: {cov:6.2f}% "
                  f"| Reward: {self._episode_reward:8.2f} "
                  f"| Bins: {int(np.sum(self._coverage_bins > 0))}/{TOTAL_BINS}")
        elif self.render_mode == "ansi":
            return self._render_ansi()

    def _render_ansi(self) -> str:
        """Return ANSI string representation."""
        cov = self._calculate_coverage()
        bar_len = 40
        filled = int(bar_len * cov / 100)
        bar = '#' * filled + '-' * (bar_len - filled)
        return (f"Coverage [{bar}] {cov:.1f}% "
                f"| Tx: {self._transaction_count} "
                f"| Bins: {int(np.sum(self._coverage_bins > 0))}/{TOTAL_BINS}")


class ALUVerifEnvContinuous(ALUVerifEnv):
    """
    Continuous action space variant for algorithms like SAC/TD3.

    Actions are continuous values [0,1] that get mapped to discrete
    stimulus categories.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Override action space to continuous
        self.action_space = spaces.Box(
            low=0.0, high=1.0, shape=(4,), dtype=np.float32
        )

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Convert continuous actions to discrete and delegate."""
        discrete_action = np.array([
            int(action[0] * 4.99),    # A category: 0-4
            int(action[1] * 4.99),    # B category: 0-4
            int(action[2] * 5.99),    # op_code: 0-5
            int(action[3] * 1.99),    # C_in: 0-1
        ], dtype=np.int64)
        return super().step(discrete_action)
