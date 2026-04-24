"""
RL Environment for ALU Verification using OpenAI Gymnasium
Implements a custom Gym environment for ALU stimulus generation optimization

The environment models the ALU verification as a reinforcement learning problem:
- State: Current coverage metrics and DUT state
- Action: Stimulus parameters (A, B, op_code, C_in)
- Reward: Based on coverage increase and bug discovery

Author: AI Assistant
Date: 2026-04-24
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import logging

logger = logging.getLogger('ALU_RL_Environment')


@dataclass
class ALUState:
    """Represents the current state of ALU verification"""
    coverage_bins: np.ndarray
    total_transactions: int
    bug_count: int
    last_op_code: int
    last_inputs: Tuple[int, int]
    coverage_percentage: float


class ALUVerificationEnv(gym.Env):
    """
    Custom Gymnasium environment for ALU Verification Optimization
    
    This environment wraps the ALU verification process to enable reinforcement
    learning-based stimulus generation. The goal is to:
    1. Maximize code coverage in minimal simulation cycles
    2. Discover corner cases efficiently
    3. Minimize time to coverage closure
    
    Action Space: MultiDiscrete
    - op_code: 6 operations (ADD, SUB, MULT, DIV, AND, XOR)
    - input_a: 8-bit input (256 values)
    - input_b: 8-bit input (256 values)
    - c_in: 2 values (0 or 1)
    
    Observation Space: Box
    - Coverage vector (12 dimensions)
    - Transaction count
    - Bug count
    - Last operation info
    """
    
    metadata = {'render_modes': ['human', 'rgb_array']}
    
    def __init__(
        self,
        max_transactions: int = 100000,
        coverage_bins: int = 12,
        enable_shaping: bool = True,
        exploration_bonus: float = 0.1,
        bug_bonus: float = 10.0,
        coverage_threshold: float = 0.95
    ):
        """
        Initialize ALU Verification Environment
        
        Args:
            max_transactions: Maximum number of transactions before termination
            coverage_bins: Number of coverage bins to track
            enable_shaping: Enable reward shaping
            exploration_bonus: Bonus for exploring new coverage regions
            bug_bonus: Reward bonus for discovering bugs
            coverage_threshold: Coverage threshold for success
        """
        super().__init__()
        
        # Configuration
        self.max_transactions = max_transactions
        self.coverage_bins = coverage_bins
        self.enable_shaping = enable_shaping
        self.exploration_bonus = exploration_bonus
        self.bug_bonus = bug_bonus
        self.coverage_threshold = coverage_threshold
        
        # Define action space: [op_code, A, B, C_in]
        self.action_space = spaces.MultiDiscrete([
            6,      # op_code: 0-5
            256,    # A: 0-255
            256,    # B: 0-255
            2       # C_in: 0-1
        ])
        
        # Define observation space
        # Coverage vector + status info
        self.observation_space = spaces.Box(
            low=0,
            high=1,
            shape=(coverage_bins + 5,),  # coverage + transaction_count + bug_count + op_code + A + B
            dtype=np.float32
        )
        
        # Internal state
        self._reset_internal_state()
        
        logger.info(f"ALU Verification Environment initialized")
        logger.info(f"Action space: {self.action_space}")
        logger.info(f"Observation space: {self.observation_space}")
    
    def _reset_internal_state(self):
        """Reset internal state variables"""
        self.transaction_count = 0
        self.bug_count = 0
        self.coverage_vector = np.zeros(self.coverage_bins, dtype=np.float32)
        self.visited_states = set()
        self.last_action = None
        self.last_reward = 0.0
        self.coverage_history = []
        self.total_reward = 0.0
        
        # Track op_code coverage
        self.op_code_coverage = np.zeros(6, dtype=np.float32)
        self.last_op_code = 0
        self.last_a = 0
        self.last_b = 0
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset the environment to initial state
        
        Args:
            seed: Random seed
            options: Additional options
            
        Returns:
            Initial observation and info dict
        """
        super().reset(seed=seed)
        
        if seed is not None:
            np.random.seed(seed)
        
        self._reset_internal_state()
        
        info = {
            'coverage': float(self._get_coverage_percentage()),
            'transactions': self.transaction_count,
            'bugs': self.bug_count
        }
        
        return self._get_observation(), info
    
    def step(
        self,
        action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment
        
        Args:
            action: [op_code, A, B, C_in]
            
        Returns:
            observation, reward, terminated, truncated, info
        """
        op_code, a, b, c_in = action
        
        # Store last inputs
        self.last_op_code = int(op_code)
        self.last_a = int(a)
        self.last_b = int(b)
        
        # Execute transaction
        self.transaction_count += 1
        
        # Calculate coverage update
        old_coverage = self._get_coverage_percentage()
        
        # Update coverage based on operation
        self._update_coverage(int(op_code), int(a), int(b))
        
        new_coverage = self._get_coverage_percentage()
        coverage_increase = new_coverage - old_coverage
        
        # Calculate reward
        reward = self._calculate_reward(coverage_increase, op_code, a, b)
        
        # Update last action
        self.last_action = action
        
        # Check termination conditions
        terminated = False
        truncated = False
        
        # Termination if coverage threshold reached
        if new_coverage >= self.coverage_threshold:
            terminated = True
            logger.info(f"Coverage threshold {self.coverage_threshold} reached!")
            reward += 100.0  # Success bonus
        
        # Truncation if max transactions reached
        if self.transaction_count >= self.max_transactions:
            truncated = True
        
        # Build info dict
        info = {
            'coverage': float(new_coverage),
            'transactions': self.transaction_count,
            'bugs': self.bug_count,
            'coverage_increase': float(coverage_increase),
            'op_code': int(op_code),
            'A': int(a),
            'B': int(b)
        }
        
        # Track stats
        self.coverage_history.append(new_coverage)
        self.total_reward += reward
        
        return self._get_observation(), reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation"""
        coverage_pct = self._get_coverage_percentage()
        
        # Normalize coverage vector
        normalized_coverage = self.coverage_vector.copy()
        
        # Add status info
        obs = np.concatenate([
            normalized_coverage,
            np.array([
                self.transaction_count / self.max_transactions,
                self.bug_count / 10.0,  # Assume max 10 bugs
                self.last_op_code / 5.0,
                self.last_a / 255.0,
                self.last_b / 255.0
            ], dtype=np.float32)
        ])
        
        return obs
    
    def _get_coverage_percentage(self) -> float:
        """Calculate overall coverage percentage"""
        if len(self.coverage_vector) == 0:
            return 0.0
        return float(np.mean(self.coverage_vector))
    
    def _update_coverage(self, op_code: int, a: int, b: int):
        """Update coverage based on operation and inputs"""
        # Update op_code coverage
        self.op_code_coverage[op_code] = 1.0
        
        # Update coverage bins
        # Bin 0: op_code coverage
        self.coverage_vector[0] = float(np.mean(self.op_code_coverage > 0))
        
        # Bin 1-6: Individual op_code coverage
        if op_code < 6:
            self.coverage_vector[1 + op_code] = 1.0
        
        # Corner cases
        # Bin 7: All ones inputs (A=255, B=255)
        if a == 255 and b == 255:
            self.coverage_vector[7] = max(self.coverage_vector[7], 1.0)
        
        # Bin 8: All zeros inputs (A=0, B=0)
        if a == 0 and b == 0:
            self.coverage_vector[8] = max(self.coverage_vector[8], 1.0)
        
        # Bin 9: Mixed patterns (one max, one min)
        if (a == 255 and b == 0) or (a == 0 and b == 255):
            self.coverage_vector[9] = max(self.coverage_vector[9], 1.0)
        
        # Bin 10: Carry-in cases
        # Bin 11: Overflow cases for arithmetic operations
        if op_code in [0, 1]:  # ADD, SUB
            # Check for carry/borrow
            if op_code == 0 and (a + b >= 256):
                self.coverage_vector[11] = max(self.coverage_vector[11], 1.0)
            if op_code == 1 and a < b:
                self.coverage_vector[11] = max(self.coverage_vector[11], 1.0)
    
    def _calculate_reward(
        self,
        coverage_increase: float,
        op_code: int,
        a: int,
        b: int
    ) -> float:
        """
        Calculate reward based on coverage and exploration
        
        Args:
            coverage_increase: Increase in coverage this step
            op_code: Operation code
            a: Input A
            b: Input B
            
        Returns:
            Reward value
        """
        reward = 0.0
        
        # Base reward for coverage
        reward += coverage_increase * 100.0
        
        # Exploration bonus for visiting new states
        state_key = (op_code, a, b)
        if state_key not in self.visited_states:
            reward += self.exploration_bonus
            self.visited_states.add(state_key)
        
        # Bonus for covering corner cases
        if a == 255 and b == 255:
            reward += 0.5
        if a == 0 and b == 0:
            reward += 0.5
        if (a == 255 and b == 0) or (a == 0 and b == 255):
            reward += 0.5
        
        # Small time penalty to encourage efficiency
        reward -= 0.01
        
        return reward
    
    def update_from_simulation(self, coverage_data: Dict[str, Any], bug_found: bool = False):
        """
        Update environment state from actual simulation results
        
        This method allows the environment to receive real coverage data
        from the UVM simulation rather than using the simulated coverage.
        
        Args:
            coverage_data: Coverage information from UVM
            bug_found: Whether a bug was detected
        """
        if bug_found:
            self.bug_count += 1
        
        # Update coverage from simulation
        if 'op_code_coverage' in coverage_data:
            for i, val in enumerate(coverage_data['op_code_coverage']):
                if val > self.op_code_coverage[i]:
                    self.op_code_coverage[i] = float(val)
                    self.coverage_vector[1 + i] = 1.0
        
        # Recalculate overall coverage
        self.coverage_vector[0] = float(np.mean(self.op_code_coverage > 0))
    
    def get_coverage_report(self) -> Dict[str, Any]:
        """Generate coverage report"""
        return {
            'overall_coverage': float(self._get_coverage_percentage()),
            'op_code_coverage': {
                'ADD': bool(self.op_code_coverage[0]),
                'SUB': bool(self.op_code_coverage[1]),
                'MULT': bool(self.op_code_coverage[2]),
                'DIV': bool(self.op_code_coverage[3]),
                'AND': bool(self.op_code_coverage[4]),
                'XOR': bool(self.op_code_coverage[5])
            },
            'total_transactions': self.transaction_count,
            'bug_count': self.bug_count,
            'unique_states': len(self.visited_states)
        }
    
    def render(self, mode: str = 'human'):
        """Render the environment (for visualization)"""
        if mode == 'human':
            print(f"\n{'='*50}")
            print(f"ALU Verification Environment State")
            print(f"{'='*50}")
            print(f"Transactions: {self.transaction_count}/{self.max_transactions}")
            print(f"Coverage: {self._get_coverage_percentage()*100:.2f}%")
            print(f"Bugs Found: {self.bug_count}")
            print(f"Unique States: {len(self.visited_states)}")
            print(f"Total Reward: {self.total_reward:.2f}")
            print(f"{'='*50}\n")
    
    def close(self):
        """Clean up environment resources"""
        logger.info("Closing ALU Verification Environment")
        self.coverage_history.clear()


class ALUVerificationEnvV2(ALUVerificationEnv):
    """
    Enhanced version of ALU Verification Environment
    Includes more sophisticated coverage tracking and reward shaping
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Enhanced tracking
        self.corner_cases_found = set()
        self.transition_count = 0
        self.efficiency_score = 0.0
        
        # Define corner cases
        self._corner_cases = [
            ('ADD', 255, 255, 0),   # Max addition
            ('ADD', 0, 0, 0),       # Zero addition
            ('ADD', 128, 128, 0),   # Midpoint + midpoint
            ('SUB', 255, 255, 0),   # Max subtraction
            ('SUB', 0, 5, 0),       # Negative result
            ('MULT', 255, 255, 0),  # Max multiplication
            ('MULT', 0, 0, 0),      # Zero multiplication
            ('DIV', 255, 255, 0),   # Max division
            ('DIV', 0, 1, 0),       # Zero / positive
            ('AND', 255, 255, 0),   # All ones AND
            ('XOR', 255, 255, 0),   # All ones XOR
        ]
    
    def _update_coverage(self, op_code: int, a: int, b: int):
        """Enhanced coverage update with corner case tracking"""
        super()._update_coverage(op_code, a, b)
        
        # Track corner cases
        op_names = ['ADD', 'SUB', 'MULT', 'DIV', 'AND', 'XOR']
        op_name = op_names[op_code] if op_code < len(op_names) else 'UNKNOWN'
        
        for i, case in enumerate(self._corner_cases):
            if op_name == case[0] and a == case[1] and b == case[2]:
                self.corner_cases_found.add(i)
                self.coverage_vector[min(7 + i, 11)] = 1.0
        
        # Track transitions between operations
        if self.last_op_code != op_code:
            self.transition_count += 1
        
        # Update efficiency score
        if self.transaction_count > 0:
            self.efficiency_score = (
                len(self.visited_states) / self.transaction_count
            )
    
    def _calculate_reward(self, coverage_increase: float, op_code: int, a: int, b: int) -> float:
        """Enhanced reward calculation with efficiency tracking"""
        reward = super()._calculate_reward(coverage_increase, op_code, a, b)
        
        # Corner case discovery bonus
        op_names = ['ADD', 'SUB', 'MULT', 'DIV', 'AND', 'XOR']
        op_name = op_names[op_code] if op_code < len(op_names) else 'UNKNOWN'
        
        for i, case in enumerate(self._corner_cases):
            if op_name == case[0] and a == case[1] and b == case[2]:
                if i not in self.corner_cases_found:
                    reward += 1.0  # New corner case found
        
        # Efficiency bonus
        reward += self.efficiency_score * 0.1
        
        # Transition diversity bonus
        if self.transition_count > 0:
            unique_ops = len(set(self.op_code_coverage > 0))
            if unique_ops > 0:
                transition_rate = self.transition_count / self.transaction_count
                if transition_rate > 0.5:
                    reward += 0.2
        
        return reward


class CoverageShapedEnv(gym.Wrapper):
    """
    Wrapper that adds coverage-based reward shaping to any ALU environment
    Provides additional feedback for moving towards unexplored regions
    """
    
    def __init__(self, env: gym.Env, shaping_coefficient: float = 0.1):
        super().__init__(env)
        self.shaping_coefficient = shaping_coefficient
        self.potential_function = PotentialBasedShaping()
    
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        # Add potential-based shaping
        if not terminated and not truncated:
            current_potential = self.potential_function.compute_potential(obs)
            prev_potential = getattr(self, '_prev_potential', current_potential)
            
            shaping_reward = self.shaping_coefficient * (
                current_potential - prev_potential
            )
            reward += shaping_reward
            
            self._prev_potential = current_potential
        
        return obs, reward, terminated, truncated, info


class PotentialBasedShaping:
    """Potential function for reward shaping based on coverage"""
    
    def __init__(self):
        self.max_coverage = 12.0  # Total coverage dimensions
    
    def compute_potential(self, obs: np.ndarray) -> float:
        """Compute potential based on observation"""
        coverage_dims = obs[:12]
        return float(np.sum(coverage_dims)) / self.max_coverage


def create_alu_env(
    env_config: Optional[Dict[str, Any]] = None,
    use_v2: bool = False,
    add_shaping: bool = False
) -> gym.Env:
    """
    Factory function to create configured ALU verification environment
    
    Args:
        env_config: Environment configuration dict
        use_v2: Use V2 environment
        add_shaping: Add coverage shaping wrapper
        
    Returns:
        Configured Gymnasium environment
    """
    config = env_config or {}
    
    if use_v2:
        base_env = ALUVerificationEnvV2(**config)
    else:
        base_env = ALUVerificationEnv(**config)
    
    if add_shaping:
        base_env = CoverageShapedEnv(base_env)
    
    return base_env