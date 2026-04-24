"""
RL Agents Module for ALU Verification
Provides multiple reinforcement learning algorithms using stable-baselines3

Supported algorithms:
- PPO (Proximal Policy Optimization)
- A2C (Advantage Actor-Critic)
- DQN (Deep Q-Network)
- SAC (Soft Actor-Critic)
- TD3 (Twin Delayed DDPG)

Author: AI Assistant
Date: 2026-04-24
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, Type
from dataclasses import dataclass
from enum import Enum
import numpy as np
import gymnasium as gym

try:
    from stable_baselines3 import PPO, A2C, DQN, SAC, TD3
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import EvalCallback, BaseCallback
    from stable_baselines3.common.monitor import Monitor
    STABLE_BASELINES3_AVAILABLE = True
except ImportError:
    STABLE_BASELINES3_AVAILABLE = False
    PPO = A2C = DQN = SAC = TD3 = None

logger = logging.getLogger('RL_Agents')


class AlgorithmType(Enum):
    """Supported RL algorithms"""
    PPO = "ppo"
    A2C = "a2c"
    DQN = "dqn"
    SAC = "sac"
    TD3 = "td3"
    RANDOM = "random"


@dataclass
class TrainingConfig:
    """Configuration for RL training"""
    total_timesteps: int = 100000
    eval_freq: int = 10000
    n_eval_episodes: int = 10
    save_freq: int = 50000
    log_interval: int = 100
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.0
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    target_steps_per_episode: int = 1000
    coverage_target: float = 0.95


class CoverageCallback(BaseCallback):
    """
    Custom callback for monitoring coverage progress during training
    Saves best models based on coverage efficiency
    """
    
    def __init__(
        self,
        check_freq: int = 1000,
        coverage_target: float = 0.95,
        save_path: str = './models',
        verbose: int = 1
    ):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.coverage_target = coverage_target
        self.save_path = save_path
        self.best_coverage = 0.0
        self.best_efficiency = 0.0
        
        os.makedirs(save_path, exist_ok=True)
    
    def _on_step(self) -> bool:
        """Called at each step"""
        if self.n_calls % self.check_freq == 0:
            # Get coverage from environment
            if hasattr(self.training_env, 'envs') and len(self.training_env.envs) > 0:
                env = self.training_env.envs[0]
                if hasattr(env, 'unwrapped'):
                    coverage = env.unwrapped._get_coverage_percentage()
                    transactions = env.unwrapped.transaction_count
                    
                    if transactions > 0:
                        efficiency = (env.unwrapped._get_coverage_percentage() * 1000) / transactions
                        
                        if self.verbose > 0:
                            print(f"Step {self.n_calls}: Coverage={coverage:.2%}, "
                                  f"Transactions={transactions}, Efficiency={efficiency:.4f}")
                        
                        # Save if best coverage
                        if coverage > self.best_coverage:
                            self.best_coverage = coverage
                            if self.verbose > 0:
                                print(f"New best coverage: {coverage:.2%}")
                            
                            self.model.save(os.path.join(self.save_path, 'best_coverage_model'))
                        
                        # Check if target reached
                        if coverage >= self.coverage_target:
                            if self.verbose > 0:
                                print(f"Coverage target {self.coverage_target:.2%} reached!")
                            return False
        
        return True


class TrainingStatisticsCallback(BaseCallback):
    """Callback for tracking detailed training statistics"""
    
    def __init__(self, verbose: int = 1):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.coverage_history = []
        self.efficiency_history = []
    
    def _on_step(self) -> bool:
        """Track statistics at each step"""
        if len(self.locals.get('infos', [])) > 0:
            for info in self.locals['infos']:
                if 'episode' in info:
                    self.episode_rewards.append(info['episode']['r'])
                    self.episode_lengths.append(info['episode']['l'])
                if 'coverage' in info:
                    self.coverage_history.append(info['coverage'])
                    transactions = info.get('transactions', 1)
                    if transactions > 0:
                        efficiency = info['coverage'] * 1000 / transactions
                        self.efficiency_history.append(efficiency)
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get training statistics"""
        return {
            'mean_reward': float(np.mean(self.episode_rewards)) if self.episode_rewards else 0.0,
            'std_reward': float(np.std(self.episode_rewards)) if self.episode_rewards else 0.0,
            'mean_length': float(np.mean(self.episode_lengths)) if self.episode_lengths else 0.0,
            'max_coverage': float(max(self.coverage_history)) if self.coverage_history else 0.0,
            'mean_efficiency': float(np.mean(self.efficiency_history)) if self.efficiency_history else 0.0,
            'total_episodes': len(self.episode_rewards)
        }


class RLAgent:
    """
    Base class for RL agents for ALU verification
    Wraps stable-baselines3 algorithms with ALU-specific functionality
    """
    
    def __init__(
        self,
        env: gym.Env,
        algorithm: AlgorithmType = AlgorithmType.PPO,
        model_dir: str = './models',
        config: Optional[TrainingConfig] = None
    ):
        """
        Initialize RL Agent
        
        Args:
            env: Gymnasium environment
            algorithm: RL algorithm to use
            model_dir: Directory for saving models
            config: Training configuration
        """
        if not STABLE_BASELINES3_AVAILABLE:
            raise ImportError("stable-baselines3 is not installed. Install with: pip install stable-baselines3")
        
        self.env = env
        self.algorithm = algorithm
        self.model_dir = model_dir
        self.config = config or TrainingConfig()
        self.model = None
        self.is_trained = False
        
        os.makedirs(model_dir, exist_ok=True)
        
        logger.info(f"Initialized {algorithm.value} agent")
    
    def _get_algorithm_kwargs(self) -> Dict[str, Any]:
        """Get algorithm-specific hyperparameters"""
        base_kwargs = {
            'learning_rate': self.config.learning_rate,
            'gamma': self.config.gamma,
            'verbose': 1
        }
        
        if self.algorithm == AlgorithmType.PPO:
            return {
                **base_kwargs,
                'n_steps': self.config.n_steps,
                'batch_size': self.config.batch_size,
                'n_epochs': self.config.n_epochs,
                'gae_lambda': self.config.gae_lambda,
                'clip_range': self.config.clip_range,
                'ent_coef': self.config.ent_coef,
                'vf_coef': self.config.vf_coef,
                'max_grad_norm': self.config.max_grad_norm
            }
        elif self.algorithm == AlgorithmType.A2C:
            return {
                **base_kwargs,
                'n_steps': self.config.n_steps,
                'gae_lambda': self.config.gae_lambda,
                'ent_coef': self.config.ent_coef,
                'vf_coef': self.config.vf_coef
            }
        elif self.algorithm == AlgorithmType.DQN:
            return {
                **base_kwargs,
                'buffer_size': 100000,
                'learning_starts': 1000,
                'batch_size': self.config.batch_size,
                'tau': 1.0,
                'gamma': self.config.gamma,
                'train_freq': 4,
                'gradient_steps': 1,
                'target_update_interval': 1000
            }
        elif self.algorithm == AlgorithmType.SAC:
            return {
                **base_kwargs,
                'buffer_size': 100000,
                'learning_starts': 1000,
                'batch_size': self.config.batch_size,
                'tau': 0.005,
                'ent_coef': self.config.ent_coef
            }
        elif self.algorithm == AlgorithmType.TD3:
            return {
                **base_kwargs,
                'buffer_size': 100000,
                'learning_starts': 1000,
                'batch_size': self.config.batch_size,
                'tau': 0.005
            }
        
        return base_kwargs
    
    def create_model(self) -> Any:
        """Create the RL model based on algorithm"""
        policy = 'MlpPolicy'
        
        if self.algorithm == AlgorithmType.PPO:
            self.model = PPO(policy, self.env, **self._get_algorithm_kwargs())
        elif self.algorithm == AlgorithmType.A2C:
            self.model = A2C(policy, self.env, **self._get_algorithm_kwargs())
        elif self.algorithm == AlgorithmType.DQN:
            self.model = DQN(policy, self.env, **self._get_algorithm_kwargs())
        elif self.algorithm == AlgorithmType.SAC:
            self.model = SAC(policy, self.env, **self._get_algorithm_kwargs())
        elif self.algorithm == AlgorithmType.TD3:
            self.model = TD3(policy, self.env, **self._get_algorithm_kwargs())
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
        
        logger.info(f"Created {self.algorithm.value} model")
        return self.model
    
    def train(self, eval_env: Optional[gym.Env] = None) -> Dict[str, Any]:
        """
        Train the RL agent
        
        Args:
            eval_env: Environment for evaluation during training
            
        Returns:
            Training statistics dictionary
        """
        if self.model is None:
            self.create_model()
        
        callbacks = [
            CoverageCallback(
                coverage_target=self.config.coverage_target,
                save_path=self.model_dir
            ),
            TrainingStatisticsCallback()
        ]
        
        if eval_env:
            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=self.model_dir,
                log_path=self.model_dir,
                eval_freq=self.config.eval_freq,
                n_eval_episodes=self.config.n_eval_episodes,
                deterministic=True,
                render=False
            )
            callbacks.append(eval_callback)
        
        logger.info(f"Starting training for {self.config.total_timesteps} timesteps")
        
        self.model.learn(
            total_timesteps=self.config.total_timesteps,
            callback=callbacks,
            log_interval=self.config.log_interval,
            progress_bar=True
        )
        
        self.is_trained = True
        
        # Get statistics from last callback
        stats_callback = callbacks[1]
        stats = stats_callback.get_statistics()
        stats['algorithm'] = self.algorithm.value
        stats['total_timesteps'] = self.config.total_timesteps
        
        logger.info(f"Training complete. Best coverage: {stats.get('max_coverage', 0):.2%}")
        
        return stats
    
    def save(self, path: Optional[str] = None):
        """Save the trained model"""
        save_path = path or os.path.join(self.model_dir, f'{self.algorithm.value}_model')
        if self.model:
            self.model.save(save_path)
            logger.info(f"Model saved to {save_path}")
    
    def load(self, path: str):
        """Load a trained model"""
        if self.algorithm == AlgorithmType.PPO:
            self.model = PPO.load(path)
        elif self.algorithm == AlgorithmType.A2C:
            self.model = A2C.load(path)
        elif self.algorithm == AlgorithmType.DQN:
            self.model = DQN.load(path)
        elif self.algorithm == AlgorithmType.SAC:
            self.model = SAC.load(path)
        elif self.algorithm == AlgorithmType.TD3:
            self.model = TD3.load(path)
        else:
            raise ValueError(f"Cannot load unknown algorithm: {self.algorithm}")
        
        self.is_trained = True
        logger.info(f"Model loaded from {path}")
    
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[np.ndarray, float]:
        """
        Predict action based on observation
        
        Args:
            observation: Current observation
            deterministic: Use deterministic policy
            
        Returns:
            Action and state value
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained or loaded before prediction")
        
        return self.model.predict(observation, deterministic=deterministic)
    
    def generate_stimulus(self, observation: np.ndarray) -> Dict[str, int]:
        """
        Generate ALU stimulus from observation
        
        Args:
            observation: Current observation
            
        Returns:
            Stimulus dictionary with A, B, op_code, C_in
        """
        action, _ = self.predict(observation)
        
        return {
            'A': int(action[1]),      # A value
            'B': int(action[2]),      # B value
            'op_code': int(action[0]), # Operation code
            'C_in': int(action[3])     # Carry input
        }


class RandomAgent:
    """
    Baseline random agent for comparison
    Generates random stimuli without learning
    """
    
    def __init__(self, env: gym.Env):
        self.env = env
        self.is_trained = True  # Always "trained"
    
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[np.ndarray, float]:
        """Generate random action"""
        action = self.env.action_space.sample()
        return action, 0.0
    
    def generate_stimulus(self, observation: np.ndarray) -> Dict[str, int]:
        """Generate random ALU stimulus"""
        action, _ = self.predict(observation)
        return {
            'A': int(action[1]),
            'B': int(action[2]),
            'op_code': int(action[0]),
            'C_in': int(action[3])
        }
    
    def save(self, path: str):
        """Save agent (no-op for random agent)"""
        pass
    
    def load(self, path: str):
        """Load agent (no-op for random agent)"""
        pass


class AdaptiveAgent:
    """
    Adaptive agent that combines RL with heuristic exploration
    Uses coverage feedback to guide exploration
    """
    
    def __init__(
        self,
        env: gym.Env,
        base_agent: RLAgent,
        exploration_weight: float = 0.2,
        coverage_weight: float = 0.3
    ):
        self.env = env
        self.base_agent = base_agent
        self.exploration_weight = exploration_weight
        self.coverage_weight = coverage_weight
        
        # Track exploration
        self.op_code_counts = np.zeros(6)
        self.total_count = 0
    
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[np.ndarray, float]:
        """
        Generate action with adaptive exploration
        """
        # Get base agent prediction
        base_action, value = self.base_agent.predict(observation, deterministic)
        
        if deterministic:
            return base_action, value
        
        # Adaptive exploration: bias towards less-explored operations
        action = base_action.copy()
        op_code_idx = int(action[0])
        
        # Calculate exploration probabilities (inverse of counts)
        probs = 1.0 / (self.op_code_counts + 1)
        probs /= probs.sum()
        
        # Occasionally choose different operation
        if np.random.random() < self.exploration_weight:
            action[0] = np.random.choice(6, p=probs)
        
        return action, value
    
    def update_exploration(self, action: np.ndarray, coverage: float):
        """
        Update exploration statistics
        
        Args:
            action: Action that was taken
            coverage: Resulting coverage
        """
        op_code = int(action[0])
        self.op_code_counts[op_code] += 1
        self.total_count += 1
    
    def generate_stimulus(self, observation: np.ndarray) -> Dict[str, int]:
        """Generate stimulus with adaptive exploration"""
        action, _ = self.predict(observation)
        self.update_exploration(action, observation[0])
        
        return {
            'A': int(action[1]),
            'B': int(action[2]),
            'op_code': int(action[0]),
            'C_in': int(action[3])
        }


class EnsembleAgent:
    """
    Ensemble of multiple agents for more robust stimulus generation
    Combines predictions from multiple algorithms
    """
    
    def __init__(self, agents: list, voting: str = 'majority'):
        """
        Initialize ensemble
        
        Args:
            agents: List of RLAgent instances
            voting: Voting strategy ('majority', 'weighted', 'best')
        """
        self.agents = agents
        self.voting = voting
    
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[np.ndarray, float]:
        """Aggregate predictions from all agents"""
        predictions = []
        values = []
        
        for agent in self.agents:
            action, value = agent.predict(observation, deterministic)
            predictions.append(action)
            values.append(value)
        
        # Aggregate op_code separately (categorical)
        op_codes = [p[0] for p in predictions]
        
        if self.voting == 'majority':
            # Mode of op_code
            op_code_vote = int(np.median(op_codes))
        else:
            op_code_vote = int(np.mean(op_codes))
        
        # Average continuous values
        a_val = int(np.mean([p[1] for p in predictions]))
        b_val = int(np.mean([p[2] for p in predictions]))
        c_in = int(np.round(np.mean([p[3] for p in predictions])))
        
        ensemble_action = np.array([op_code_vote, a_val, b_val, c_in])
        mean_value = np.mean(values)
        
        return ensemble_action, mean_value
    
    def generate_stimulus(self, observation: np.ndarray) -> Dict[str, int]:
        """Generate ensemble stimulus"""
        action, _ = self.predict(observation)
        return {
            'A': int(action[1]),
            'B': int(action[2]),
            'op_code': int(action[0]),
            'C_in': int(action[3])
        }


def create_agent(
    env: gym.Env,
    algorithm: AlgorithmType = AlgorithmType.PPO,
    model_dir: str = './models',
    config: Optional[TrainingConfig] = None
) -> RLAgent:
    """
    Factory function to create an RL agent
    
    Args:
        env: Gymnasium environment
        algorithm: Algorithm type
        model_dir: Model save directory
        config: Training configuration
        
    Returns:
        Configured RL agent
    """
    if algorithm == AlgorithmType.RANDOM:
        return RandomAgent(env)
    
    return RLAgent(env, algorithm, model_dir, config)


def compare_agents(
    env: gym.Env,
    algorithms: list,
    episodes: int = 10,
    max_steps: int = 10000
) -> Dict[str, Dict[str, float]]:
    """
    Compare multiple algorithms on the ALU verification task
    
    Args:
        env: Gymnasium environment
        algorithms: List of AlgorithmType values
        episodes: Number of episodes to evaluate
        max_steps: Maximum steps per episode
        
    Returns:
        Dictionary of results per algorithm
    """
    results = {}
    
    for algo in algorithms:
        print(f"\nEvaluating {algo.value}...")
        
        agent = create_agent(env, algo)
        
        episode_rewards = []
        episode_lengths = []
        coverages = []
        
        for ep in range(episodes):
            obs, _ = env.reset()
            episode_reward = 0
            episode_length = 0
            
            for step in range(max_steps):
                action, _ = agent.predict(obs)
                obs, reward, terminated, truncated, info = env.step(action)
                episode_reward += reward
                episode_length += 1
                
                if terminated or truncated:
                    break
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            coverages.append(info.get('coverage', 0))
        
        results[algo.value] = {
            'mean_reward': float(np.mean(episode_rewards)),
            'std_reward': float(np.std(episode_rewards)),
            'mean_length': float(np.mean(episode_lengths)),
            'mean_coverage': float(np.mean(coverages)),
            'max_coverage': float(max(coverages))
        }
        
        print(f"  Mean reward: {results[algo.value]['mean_reward']:.2f}")
        print(f"  Mean coverage: {results[algo.value]['mean_coverage']:.2%}")
    
    return results