"""
RL Training and Simulation Interface
Coordinates between RL training, simulation, and UVM testbench

This module provides:
- Training orchestration for RL agents
- Simulation control for UVM interaction
- Performance analysis and comparison tools

Author: AI Assistant
Date: 2026-04-24
"""

import os
import sys
import time
import json
import logging
import threading
import queue
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

logger = logging.getLogger('RL_Trainer')


@dataclass
class SimulationConfig:
    """Configuration for simulation runs"""
    use_ai: bool = False
    algorithm: str = "ppo"
    max_transactions: int = 100000
    server_host: str = "localhost"
    server_port: int = 5555
    connection_timeout: float = 30.0
    transaction_timeout: float = 5.0
    enable_logging: bool = True
    save_results: bool = True
    results_dir: str = "./results"


@dataclass
class TrainingResult:
    """Results from a training run"""
    algorithm: str
    total_timesteps: int
    training_time: float
    final_coverage: float
    best_coverage: float
    transactions_used: int
    mean_reward: float
    episodes_completed: int
    model_path: Optional[str]
    timestamp: str


class RLTrainer:
    """
    Orchestrates RL training for ALU verification
    Manages training loops, evaluation, and model saving
    """
    
    def __init__(
        self,
        env,
        config: Optional[TrainingConfig] = None,
        model_dir: str = "./models"
    ):
        """
        Initialize RL Trainer
        
        Args:
            env: Gymnasium environment
            config: Training configuration
            model_dir: Directory for saving models
        """
        self.env = env
        self.config = config or TrainingConfig()
        self.model_dir = model_dir
        
        os.makedirs(model_dir, exist_ok=True)
        
        self.agents: Dict[str, Any] = {}
        self.training_history: List[TrainingResult] = []
    
    def train_agent(
        self,
        algorithm: str,
        eval_env: Optional[Any] = None
    ) -> TrainingResult:
        """
        Train a single agent
        
        Args:
            algorithm: Algorithm name ('ppo', 'a2c', 'dqn', 'sac', 'td3')
            eval_env: Optional evaluation environment
            
        Returns:
            Training result
        """
        from rl_agents import create_agent, AlgorithmType
        
        algo_map = {
            'ppo': AlgorithmType.PPO,
            'a2c': AlgorithmType.A2C,
            'dqn': AlgorithmType.DQN,
            'sac': AlgorithmType.SAC,
            'td3': AlgorithmType.TD3,
            'random': AlgorithmType.RANDOM
        }
        
        algo_type = algo_map.get(algorithm.lower(), AlgorithmType.PPO)
        
        logger.info(f"Training {algorithm} agent...")
        
        # Create agent
        agent = create_agent(
            self.env,
            algo_type,
            self.model_dir,
            self.config
        )
        
        start_time = time.time()
        
        # Train
        if algo_type != AlgorithmType.RANDOM:
            stats = agent.train(eval_env)
        else:
            # For random agent, just run episodes
            stats = self._evaluate_random_agent(agent)
        
        training_time = time.time() - start_time
        
        # Save model
        model_path = os.path.join(self.model_dir, f'{algorithm}_final')
        agent.save(model_path)
        
        # Get final metrics
        final_coverage = self.env._get_coverage_percentage()
        best_coverage = max(self.env.coverage_history) if hasattr(self.env, 'coverage_history') else final_coverage
        
        result = TrainingResult(
            algorithm=algorithm,
            total_timesteps=self.config.total_timesteps,
            training_time=training_time,
            final_coverage=final_coverage,
            best_coverage=best_coverage,
            transactions_used=self.env.transaction_count,
            mean_reward=stats.get('mean_reward', 0),
            episodes_completed=stats.get('total_episodes', 0),
            model_path=model_path,
            timestamp=datetime.now().isoformat()
        )
        
        self.agents[algorithm] = agent
        self.training_history.append(result)
        
        logger.info(f"Training complete: {result}")
        
        return result
    
    def _evaluate_random_agent(self, agent) -> Dict[str, Any]:
        """Evaluate random agent for comparison"""
        episode_rewards = []
        episode_lengths = []
        
        for _ in range(10):
            obs, _ = self.env.reset()
            episode_reward = 0
            episode_length = 0
            
            for step in range(self.config.max_transactions):
                action, _ = agent.predict(obs)
                obs, reward, terminated, truncated, _ = self.env.step(action)
                episode_reward += reward
                episode_length += 1
                
                if terminated or truncated:
                    break
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
        
        return {
            'mean_reward': float(np.mean(episode_rewards)),
            'total_episodes': len(episode_rewards)
        }
    
    def train_all(
        self,
        algorithms: List[str],
        eval_env: Optional[Any] = None
    ) -> List[TrainingResult]:
        """
        Train multiple agents
        
        Args:
            algorithms: List of algorithm names
            eval_env: Optional evaluation environment
            
        Returns:
            List of training results
        """
        results = []
        
        for algo in algorithms:
            logger.info(f"\n{'='*50}")
            logger.info(f"Training {algo}")
            logger.info(f"{'='*50}")
            
            result = self.train_agent(algo, eval_env)
            results.append(result)
            
            # Reset environment for next algorithm
            self.env.reset()
        
        return results
    
    def compare_training_results(self) -> Dict[str, Any]:
        """Compare results from all trained agents"""
        if not self.training_history:
            return {}
        
        comparison = {
            'algorithms': [],
            'best_by_coverage': None,
            'fastest_by_time': None,
            'most_efficient': None
        }
        
        best_coverage = 0.0
        fastest_time = float('inf')
        best_efficiency = 0.0
        
        for result in self.training_history:
            comparison['algorithms'].append({
                'name': result.algorithm,
                'coverage': result.final_coverage,
                'time': result.training_time,
                'efficiency': result.final_coverage / result.training_time if result.training_time > 0 else 0
            })
            
            if result.final_coverage > best_coverage:
                best_coverage = result.final_coverage
                comparison['best_by_coverage'] = result.algorithm
            
            if result.training_time < fastest_time:
                fastest_time = result.training_time
                comparison['fastest_by_time'] = result.algorithm
            
            efficiency = result.final_coverage / result.training_time if result.training_time > 0 else 0
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                comparison['most_efficient'] = result.algorithm
        
        return comparison
    
    def save_results(self, path: str = "./results/training_results.json"):
        """Save training results to file"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'config': asdict(self.config),
            'results': [asdict(r) for r in self.training_history],
            'comparison': self.compare_training_results()
        }
        
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {path}")


class SimulationController:
    """
    Controls simulation runs with or without AI assistance
    Interfaces with UVM testbench via PyHDL-IF bridge
    """
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.bridge = None
        self.rl_agent = None
        self.is_connected = False
        
        os.makedirs(config.results_dir, exist_ok=True)
        
    def connect(self, bridge) -> bool:
        """
        Connect to UVM testbench via bridge
        
        Args:
            bridge: PyHDL-IF bridge instance
            
        Returns:
            True if connected successfully
        """
        try:
            bridge.connect()
            self.bridge = bridge
            self.is_connected = True
            logger.info("Connected to UVM testbench")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from UVM testbench"""
        if self.bridge:
            self.bridge.disconnect()
            self.is_connected = False
            logger.info("Disconnected from UVM testbench")
    
    def set_agent(self, agent):
        """Set RL agent for AI-assisted simulation"""
        self.rl_agent = agent
        logger.info(f"RL agent set: {type(agent).__name__}")
    
    def run_simulation(
        self,
        num_transactions: Optional[int] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run simulation with current configuration
        
        Args:
            num_transactions: Number of transactions to simulate
            verbose: Print progress
            
        Returns:
            Simulation results
        """
        max_trans = num_transactions or self.config.max_transactions
        
        results = {
            'config': asdict(self.config),
            'transactions': [],
            'start_time': time.time(),
            'end_time': None,
            'coverage': {},
            'bugs_found': 0,
            'transactions_completed': 0
        }
        
        try:
            for i in range(max_trans):
                # Get action from RL agent if AI is enabled
                if self.config.use_ai and self.rl_agent:
                    stimulus = self._generate_ai_stimulus()
                else:
                    stimulus = self._generate_random_stimulus()
                
                # Send to UVM
                if self.is_connected and self.bridge:
                    response = self.bridge.send_stimulus(
                        a=stimulus['A'],
                        b=stimulus['B'],
                        op_code=stimulus['op_code'],
                        c_in=stimulus.get('C_in', 0),
                        reset=stimulus.get('Reset', 0)
                    )
                    
                    if response:
                        results['transactions'].append({
                            'input': stimulus,
                            'output': response,
                            'timestamp': time.time()
                        })
                        
                        # Check for bugs
                        if response.get('error', False):
                            results['bugs_found'] += 1
                
                results['transactions_completed'] = i + 1
                
                if verbose and (i + 1) % 1000 == 0:
                    print(f"Completed {i + 1}/{max_trans} transactions")
        
        except Exception as e:
            logger.error(f"Simulation error: {e}")
        
        finally:
            results['end_time'] = time.time()
            results['duration'] = results['end_time'] - results['start_time']
        
        if self.config.save_results:
            self._save_results(results)
        
        return results
    
    def _generate_ai_stimulus(self) -> Dict[str, int]:
        """Generate stimulus using RL agent"""
        if not self.rl_agent:
            return self._generate_random_stimulus()
        
        try:
            return self.rl_agent.generate_stimulus(None)
        except Exception:
            return self._generate_random_stimulus()
    
    def _generate_random_stimulus(self) -> Dict[str, int]:
        """Generate random stimulus for baseline comparison"""
        return {
            'A': np.random.randint(0, 256),
            'B': np.random.randint(0, 256),
            'op_code': np.random.randint(0, 6),
            'C_in': np.random.randint(0, 2)
        }
    
    def _save_results(self, results: Dict[str, Any]):
        """Save simulation results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"simulation_{timestamp}.json"
        filepath = os.path.join(self.config.results_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {filepath}")


class ComparisonAnalyzer:
    """
    Analyzes and compares AI vs non-AI simulation results
    Generates reports and visualizations
    """
    
    def __init__(self, results_dir: str = "./results"):
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
    
    def load_results(self, filepath: str) -> Dict[str, Any]:
        """Load results from file"""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def compare_runs(
        self,
        ai_results: Dict[str, Any],
        baseline_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare AI-assisted vs baseline simulation
        
        Args:
            ai_results: Results with AI
            baseline_results: Results without AI
            
        Returns:
            Comparison analysis
        """
        analysis = {
            'ai_transactions': ai_results.get('transactions_completed', 0),
            'baseline_transactions': baseline_results.get('transactions_completed', 0),
            'ai_bugs_found': ai_results.get('bugs_found', 0),
            'baseline_bugs_found': baseline_results.get('bugs_found', 0),
            'ai_duration': ai_results.get('duration', 0),
            'baseline_duration': baseline_results.get('duration', 0),
            'ai_transactions_per_second': 0,
            'baseline_transactions_per_second': 0,
            'improvement': {}
        }
        
        # Calculate rates
        if analysis['ai_duration'] > 0:
            analysis['ai_transactions_per_second'] = (
                analysis['ai_transactions'] / analysis['ai_duration']
            )
        
        if analysis['baseline_duration'] > 0:
            analysis['baseline_transactions_per_second'] = (
                analysis['baseline_transactions'] / analysis['baseline_duration']
            )
        
        # Calculate improvements
        if analysis['baseline_duration'] > 0:
            analysis['improvement']['time_reduction'] = (
                (analysis['baseline_duration'] - analysis['ai_duration']) /
                analysis['baseline_duration'] * 100
            )
        
        if analysis['baseline_transactions'] > 0:
            analysis['improvement']['transaction_reduction'] = (
                (analysis['baseline_transactions'] - analysis['ai_transactions']) /
                analysis['baseline_transactions'] * 100
            )
        
        return analysis
    
    def generate_report(
        self,
        ai_results: Dict[str, Any],
        baseline_results: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate comparison report
        
        Args:
            ai_results: AI-assisted results
            baseline_results: Baseline results
            output_path: Optional output file path
            
        Returns:
            Report string
        """
        comparison = self.compare_runs(ai_results, baseline_results)
        
        report = """
================================================================================
                    ALU VERIFICATION COMPARISON REPORT
================================================================================

CONFIGURATION
-------------
AI-Assisted Simulation:
  - Algorithm: {ai_algo}
  - Transactions: {ai_transactions}
  - Duration: {ai_duration:.2f}s
  - Transactions/sec: {ai_rate:.2f}
  - Bugs Found: {ai_bugs}

Baseline Simulation (Random):
  - Transactions: {baseline_transactions}
  - Duration: {baseline_duration:.2f}s
  - Transactions/sec: {baseline_rate:.2f}
  - Bugs Found: {baseline_bugs}

IMPROVEMENTS
------------
Time Reduction: {time_improvement:.2f}%
Transaction Reduction: {trans_improvement:.2f}%

ANALYSIS
--------
{analysis_text}

================================================================================
""".format(
            ai_algo=ai_results.get('config', {}).get('algorithm', 'N/A'),
            ai_transactions=comparison['ai_transactions'],
            ai_duration=comparison['ai_duration'],
            ai_rate=comparison['ai_transactions_per_second'],
            ai_bugs=comparison['ai_bugs_found'],
            baseline_transactions=comparison['baseline_transactions'],
            baseline_duration=comparison['baseline_duration'],
            baseline_rate=comparison['baseline_transactions_per_second'],
            baseline_bugs=comparison['baseline_bugs_found'],
            time_improvement=comparison['improvement'].get('time_reduction', 0),
            trans_improvement=comparison['improvement'].get('transaction_reduction', 0),
            analysis_text=self._generate_analysis_text(comparison)
        )
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {output_path}")
        
        return report
    
    def _generate_analysis_text(self, comparison: Dict[str, Any]) -> str:
        """Generate detailed analysis text"""
        lines = []
        
        time_imp = comparison['improvement'].get('time_reduction', 0)
        trans_imp = comparison['improvement'].get('transaction_reduction', 0)
        
        if time_imp > 0:
            lines.append(f"- AI-assisted simulation completed {time_imp:.1f}% faster")
        else:
            lines.append("- No significant time improvement observed")
        
        if trans_imp > 0:
            lines.append(f"- AI achieved {trans_imp:.1f}% fewer transactions for similar coverage")
        else:
            lines.append("- AI did not show significant transaction efficiency")
        
        if comparison['ai_bugs_found'] > comparison['baseline_bugs_found']:
            lines.append(f"- AI discovered {comparison['ai_bugs_found'] - comparison['baseline_bugs_found']} additional bugs")
        elif comparison['baseline_bugs_found'] > comparison['ai_bugs_found']:
            lines.append("- Baseline found more bugs (may indicate over-exploration)")
        else:
            lines.append("- Both configurations found similar bugs")
        
        return "\n".join(lines)


class MultiThreadedSimulator:
    """
    Multi-threaded simulator for parallel transaction generation
    Uses thread pool for efficient stimulus generation
    """
    
    def __init__(
        self,
        num_workers: int = 4,
        queue_size: int = 1000
    ):
        self.num_workers = num_workers
        self.stimulus_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self.results_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.workers: List[threading.Thread] = []
    
    def start(self, agent=None):
        """Start worker threads"""
        self.is_running = True
        
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(agent,),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.num_workers} worker threads")
    
    def stop(self):
        """Stop worker threads"""
        self.is_running = False
        
        for worker in self.workers:
            worker.join(timeout=2.0)
        
        self.workers.clear()
        logger.info("Worker threads stopped")
    
    def _worker_loop(self, agent):
        """Worker thread loop"""
        import random
        
        while self.is_running:
            try:
                # Generate stimulus
                if agent:
                    try:
                        stimulus = agent.generate_stimulus(None)
                    except Exception:
                        stimulus = self._random_stimulus()
                else:
                    stimulus = self._random_stimulus()
                
                # Add to queue (non-blocking)
                try:
                    self.stimulus_queue.put_nowait(stimulus)
                except queue.Full:
                    pass
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _random_stimulus(self) -> Dict[str, int]:
        """Generate random stimulus"""
        import random
        return {
            'A': random.randint(0, 255),
            'B': random.randint(0, 255),
            'op_code': random.randint(0, 5),
            'C_in': random.randint(0, 1)
        }
    
    def get_stimulus(self, timeout: float = 1.0) -> Optional[Dict[str, int]]:
        """Get next stimulus from queue"""
        try:
            return self.stimulus_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def put_result(self, result: Dict[str, Any]):
        """Put result into results queue"""
        try:
            self.results_queue.put_nowait(result)
        except queue.Full:
            logger.warning("Results queue full, dropping result")


def run_training_comparison(
    env,
    algorithms: List[str],
    training_config: Optional[TrainingConfig] = None,
    model_dir: str = "./models"
) -> Dict[str, Any]:
    """
    Run complete training comparison across multiple algorithms
    
    Args:
        env: Gymnasium environment
        algorithms: List of algorithms to compare
        training_config: Training configuration
        model_dir: Model save directory
        
    Returns:
        Complete comparison results
    """
    trainer = RLTrainer(env, training_config, model_dir)
    
    print(f"\n{'='*70}")
    print("TRAINING COMPARISON")
    print(f"{'='*70}")
    
    results = trainer.train_all(algorithms)
    
    print(f"\n{'='*70}")
    print("RESULTS SUMMARY")
    print(f"{'='*70}")
    
    for result in results:
        print(f"\n{result.algorithm.upper()}")
        print(f"  Training Time: {result.training_time:.2f}s")
        print(f"  Final Coverage: {result.final_coverage:.2%}")
        print(f"  Mean Reward: {result.mean_reward:.2f}")
        print(f"  Transactions: {result.transactions_used}")
    
    # Save all results
    trainer.save_results()
    
    return {
        'results': [asdict(r) for r in results],
        'comparison': trainer.compare_training_results()
    }