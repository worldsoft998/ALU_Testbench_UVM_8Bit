"""
Sequence Management for RL Training
Python-side sequence definitions and management

Author: AI Assistant
Date: 2026-04-24
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger('Sequence_Manager')


class SequenceType(Enum):
    """Types of RL sequences"""
    RANDOM = "random"
    COVERAGE_DIRECTED = "coverage_directed"
    REWARD_MAXIMIZING = "reward_maximizing"
    EXPLORATION = "exploration"
    MIXED = "mixed"


@dataclass
class SequenceConfig:
    """Configuration for sequence generation"""
    sequence_type: SequenceType = SequenceType.MIXED
    batch_size: int = 32
    sequence_length: int = 100
    exploration_rate: float = 0.2
    coverage_weight: float = 0.5
    reward_weight: float = 0.5


class SequenceGenerator:
    """
    Generates sequences of actions for RL training
    Supports various generation strategies
    """
    
    def __init__(self, config: Optional[SequenceConfig] = None):
        self.config = config or SequenceConfig()
        self.sequence_history: List[List[int]] = []
    
    def generate_sequence(
        self,
        coverage_state: Optional[np.ndarray] = None,
        agent=None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a sequence of actions
        
        Args:
            coverage_state: Current coverage state
            agent: Optional RL agent for guided generation
            
        Returns:
            List of (op_code, A, B, C_in) tuples
        """
        if self.config.sequence_type == SequenceType.RANDOM:
            return self._generate_random()
        elif self.config.sequence_type == SequenceType.COVERAGE_DIRECTED:
            return self._generate_coverage_directed(coverage_state)
        elif self.config.sequence_type == SequenceType.REWARD_MAXIMIZING:
            return self._generate_reward_maximizing(agent)
        elif self.config.sequence_type == SequenceType.EXPLORATION:
            return self._generate_exploration()
        else:
            return self._generate_mixed(coverage_state)
    
    def _generate_random(self) -> List[Tuple[int, int, int, int]]:
        """Generate random sequence"""
        sequence = []
        for _ in range(self.config.sequence_length):
            sequence.append((
                np.random.randint(0, 6),  # op_code
                np.random.randint(0, 256),  # A
                np.random.randint(0, 256),  # B
                np.random.randint(0, 2)  # C_in
            ))
        return sequence
    
    def _generate_coverage_directed(
        self,
        coverage_state: Optional[np.ndarray]
    ) -> List[Tuple[int, int, int, int]]:
        """Generate coverage-directed sequence"""
        sequence = []
        
        if coverage_state is None:
            return self._generate_random()
        
        for _ in range(self.config.sequence_length):
            # Find least-covered dimensions
            uncovered_indices = np.where(coverage_state < 0.5)[0]
            
            if len(uncovered_indices) > 0:
                # Target uncovered regions
                op_code = uncovered_indices[0] % 6
            else:
                op_code = np.random.randint(0, 6)
            
            # Generate inputs based on coverage
            if np.random.random() < self.config.exploration_rate:
                # Random exploration
                A = np.random.randint(0, 256)
                B = np.random.randint(0, 256)
            else:
                # Targeted inputs
                A, B = self._get_targeted_inputs(op_code, coverage_state)
            
            C_in = np.random.randint(0, 2)
            
            sequence.append((op_code, A, B, C_in))
        
        return sequence
    
    def _generate_reward_maximizing(self, agent) -> List[Tuple[int, int, int, int]]:
        """Generate reward-maximizing sequence using agent"""
        if agent is None:
            return self._generate_random()
        
        sequence = []
        obs = None
        
        for _ in range(self.config.sequence_length):
            if obs is not None:
                action, _ = agent.predict(obs)
                sequence.append((
                    int(action[0]),
                    int(action[1]),
                    int(action[2]),
                    int(action[3])
                ))
            else:
                sequence.append((
                    np.random.randint(0, 6),
                    np.random.randint(0, 256),
                    np.random.randint(0, 256),
                    np.random.randint(0, 2)
                ))
        
        return sequence
    
    def _generate_exploration(self) -> List[Tuple[int, int, int, int]]:
        """Generate exploration-focused sequence"""
        sequence = []
        
        for _ in range(self.config.sequence_length):
            # Focus on corner cases
            corner_case = np.random.choice([
                (0, 255, 255, 0),   # Max ADD
                (0, 0, 0, 0),       # Zero ADD
                (1, 255, 1, 0),     # Mixed ADD
                (2, 255, 255, 0),   # Max MULT
                (3, 128, 2, 0),     # DIV
                (4, 255, 255, 0),   # Max AND
                (5, 255, 255, 0),   # Max XOR
            ])
            
            # Add some noise
            if np.random.random() < 0.3:
                op_code, A, B, C_in = corner_case
                A = (A + np.random.randint(-10, 11)) % 256
                B = (B + np.random.randint(-10, 11)) % 256
            else:
                op_code, A, B, C_in = corner_case
            
            sequence.append((op_code, A, B, C_in))
        
        return sequence
    
    def _generate_mixed(
        self,
        coverage_state: Optional[np.ndarray]
    ) -> List[Tuple[int, int, int, int]]:
        """Generate mixed strategy sequence"""
        sequence = []
        
        for i in range(self.config.sequence_length):
            # Mix strategies based on progress
            if i % 10 < 7:
                # 70% coverage-directed
                sub_seq = self._generate_coverage_directed(coverage_state)
                sequence.extend(sub_seq[:3])
            else:
                # 30% exploration
                sub_seq = self._generate_exploration()
                sequence.append(sub_seq[0])
        
        return sequence[:self.config.sequence_length]
    
    def _get_targeted_inputs(
        self,
        op_code: int,
        coverage_state: np.ndarray
    ) -> Tuple[int, int]:
        """Get targeted input values"""
        # Based on operation, target specific inputs
        if op_code == 0:  # ADD
            # Target overflow cases
            return 200, 100
        elif op_code == 1:  # SUB
            # Target borrow cases
            return 50, 200
        elif op_code == 2:  # MULT
            # Target overflow
            return 100, 100
        elif op_code == 3:  # DIV
            # Target edge cases
            return 255, 1
        else:
            # Logic operations - all patterns matter
            if np.random.random() < 0.5:
                return 255, 255
            else:
                return 0, 0
    
    def add_to_history(self, sequence: List[Tuple[int, int, int, int]]):
        """Add sequence to history"""
        self.sequence_history.append(sequence)
        if len(self.sequence_history) > 100:
            self.sequence_history.pop(0)
    
    def get_sequence_stats(self) -> Dict[str, Any]:
        """Get statistics about generated sequences"""
        if not self.sequence_history:
            return {}
        
        total_actions = sum(len(s) for s in self.sequence_history)
        
        return {
            'total_sequences': len(self.sequence_history),
            'total_actions': total_actions,
            'avg_sequence_length': total_actions / len(self.sequence_history)
        }


class ReplayBuffer:
    """
    Experience replay buffer for RL training
    Stores (state, action, reward, next_state, done) tuples
    """
    
    def __init__(self, capacity: int = 100000):
        self.capacity = capacity
        self.buffer: List[Dict[str, Any]] = []
        self.position = 0
    
    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Add experience to buffer"""
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done
        }
        
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int) -> List[Dict[str, Any]]:
        """Sample random batch"""
        return np.random.choice(self.buffer, batch_size, replace=False).tolist()
    
    def __len__(self) -> int:
        return len(self.buffer)
    
    def clear(self):
        """Clear buffer"""
        self.buffer.clear()
        self.position = 0