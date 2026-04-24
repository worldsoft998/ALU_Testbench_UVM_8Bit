#!/usr/bin/env python3
"""
RL Server for ALU Verification
Hosts RL agents and communicates with UVM testbench via PyHDL-IF bridge

This server:
- Loads trained RL models or trains new ones
- Accepts connections from UVM testbench
- Responds to stimulus requests with AI-generated values
- Sends coverage feedback and reward signals

Author: AI Assistant
Date: 2026-04-24
"""

import argparse
import logging
import signal
import sys
import threading
import time
from typing import Optional, Dict, Any
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RL_Server')


class RLServer:
    """
    RL Server that hosts RL agents for ALU verification
    Provides API for UVM testbench communication
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5555,
        algorithm: str = 'ppo',
        model_path: Optional[str] = None,
        use_preference_agent: bool = False
    ):
        """
        Initialize RL Server
        
        Args:
            host: Host to bind to
            port: Port to listen on
            algorithm: RL algorithm to use
            model_path: Path to pre-trained model
            use_preference_agent: Use preference-based learning
        """
        self.host = host
        self.port = port
        self.algorithm = algorithm
        self.model_path = model_path
        
        # Components
        self.bridge = None
        self.agent = None
        self.env = None
        self.server_socket = None
        
        # State
        self.is_running = False
        self.connections: list = []
        
        # Statistics
        self.request_count = 0
        self.start_time = time.time()
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize RL environment and agent"""
        try:
            # Import RL modules
            from RL.alu_rl_environment import create_alu_env
            from RL.rl_agents import create_agent, AlgorithmType, TrainingConfig
            
            # Create environment
            logger.info("Creating ALU verification environment...")
            self.env = create_alu_env({
                'max_transactions': 100000,
                'coverage_bins': 12
            })
            
            # Get algorithm type
            algo_map = {
                'ppo': AlgorithmType.PPO,
                'a2c': AlgorithmType.A2C,
                'dqn': AlgorithmType.DQN,
                'sac': AlgorithmType.SAC,
                'td3': AlgorithmType.TD3,
                'random': AlgorithmType.RANDOM
            }
            algo_type = algo_map.get(self.algorithm.lower(), AlgorithmType.PPO)
            
            # Create or load agent
            if self.model_path and self.algorithm != 'random':
                logger.info(f"Loading trained model from {self.model_path}")
                self.agent = create_agent(self.env, algo_type, './models')
                try:
                    self.agent.load(self.model_path)
                    logger.info("Model loaded successfully")
                except Exception as e:
                    logger.warning(f"Could not load model: {e}, will train new agent")
                    self.agent = create_agent(self.env, algo_type, './models')
            else:
                logger.info(f"Creating new {self.algorithm} agent")
                config = TrainingConfig()
                config.total_timesteps = 50000  # Pre-training steps
                self.agent = create_agent(self.env, algo_type, './models', config)
            
            # Pre-train agent if needed
            if not self.agent.is_trained:
                logger.info("Pre-training agent...")
                self.agent.train()
                self.agent.save()
                logger.info("Pre-training complete")
            
            # Initialize bridge
            from Bridge.pyhdl_if_bridge import PyHDLIFBridge, MessageType
            
            self.bridge = PyHDLIFBridge(
                host=self.host,
                port=self.port,
                timeout=5.0,
                enable_logging=True
            )
            
            logger.info(f"RL components initialized for {self.algorithm}")
            
        except ImportError as e:
            logger.error(f"Failed to import RL modules: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def start(self):
        """Start the RL server"""
        import socket
        
        logger.info(f"Starting RL server on {self.host}:{self.port}")
        
        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOCKET, socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.is_running = True
        
        logger.info("RL Server started successfully")
        logger.info("Waiting for UVM testbench connection...")
        
        # Start request handling thread
        request_thread = threading.Thread(target=self._handle_requests, daemon=True)
        request_thread.start()
        
        # Main loop
        try:
            while self.is_running:
                try:
                    self.server_socket.settimeout(1.0)
                    client, addr = self.server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    
                    self.connections.append(client)
                    
                    # Start client handler
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client, addr),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        logger.error(f"Error accepting connection: {e}")
        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def _handle_client(self, client: socket.socket, addr):
        """Handle a single client connection"""
        try:
            while self.is_running:
                # Receive message length
                header = client.recv(4)
                if not header:
                    break
                
                length = int.from_bytes(header, 'big')
                
                # Receive message
                data = b''
                while len(data) < length:
                    chunk = client.recv(length - len(data))
                    if not chunk:
                        break
                    data += chunk
                
                if not data:
                    break
                
                # Parse message
                message = json.loads(data.decode('utf-8'))
                response = self._process_message(message)
                
                # Send response
                if response:
                    response_data = json.dumps(response).encode('utf-8')
                    response_header = len(response_data).to_bytes(4, 'big')
                    client.sendall(response_header + response_data)
                
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            try:
                client.close()
            except:
                pass
            if client in self.connections:
                self.connections.remove(client)
            logger.info(f"Client {addr} disconnected")
    
    def _process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming message and generate response"""
        msg_type = message.get('msg_type', '')
        
        self.request_count += 1
        
        if msg_type == 'STIMULUS':
            return self._handle_stimulus_request(message)
        elif msg_type == 'COVERAGE':
            return self._handle_coverage_update(message)
        elif msg_type == 'ACTION':
            return self._handle_action_request(message)
        elif msg_type == 'TERMINATE':
            self.is_running = False
            return {'status': 'terminated'}
        else:
            return {'error': f'Unknown message type: {msg_type}'}
    
    def _handle_stimulus_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stimulus generation request"""
        try:
            # Get coverage state from message
            coverage_state = message.get('coverage_state', {})
            
            # Get observation from environment
            obs, _ = self.env.reset()
            
            # Update environment with coverage feedback
            if coverage_state:
                self.env.update_from_simulation(coverage_state)
            
            # Generate action
            action, _ = self.agent.predict(obs)
            
            # Execute action in environment
            obs, reward, terminated, truncated, info = self.env.step(action)
            
            # Extract stimulus values
            stimulus = {
                'A': int(action[1]),
                'B': int(action[2]),
                'op_code': int(action[0]),
                'C_in': int(action[3])
            }
            
            return {
                'status': 'ok',
                'stimulus': stimulus,
                'reward': float(reward),
                'coverage': float(info.get('coverage', 0)),
                'transaction': self.env.transaction_count
            }
            
        except Exception as e:
            logger.error(f"Error generating stimulus: {e}")
            return {'error': str(e)}
    
    def _handle_coverage_update(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle coverage data from UVM"""
        try:
            coverage_data = message.get('coverage', {})
            
            # Update environment
            self.env.update_from_simulation(coverage_data)
            
            return {
                'status': 'ok',
                'acknowledged': True
            }
            
        except Exception as e:
            logger.error(f"Error updating coverage: {e}")
            return {'error': str(e)}
    
    def _handle_action_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle action request from UVM"""
        try:
            coverage_state = message.get('coverage_state', {})
            
            # Get observation
            obs, _ = self.env.reset()
            
            # Update with coverage state
            if coverage_state:
                self.env.update_from_simulation(coverage_state)
            
            # Get action
            action, _ = self.agent.predict(obs)
            
            return {
                'status': 'ok',
                'action': {
                    'A': int(action[1]),
                    'B': int(action[2]),
                    'op_code': int(action[0]),
                    'C_in': int(action[3])
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating action: {e}")
            return {'error': str(e)}
    
    def _handle_requests(self):
        """Background thread for request handling"""
        while self.is_running:
            time.sleep(0.1)
    
    def stop(self):
        """Stop the RL server"""
        logger.info("Stopping RL server...")
        
        self.is_running = False
        
        # Close all connections
        for client in self.connections:
            try:
                client.close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Print statistics
        uptime = time.time() - self.start_time
        logger.info(f"RL Server stopped")
        logger.info(f"Statistics:")
        logger.info(f"  Requests handled: {self.request_count}")
        logger.info(f"  Uptime: {uptime:.2f}s")
        logger.info(f"  Final coverage: {self.env._get_coverage_percentage():.2%}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='RL Server for ALU Verification'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='Host to bind to (default: localhost)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5555,
        help='Port to listen on (default: 5555)'
    )
    
    parser.add_argument(
        '--algorithm',
        type=str,
        default='ppo',
        choices=['ppo', 'a2c', 'dqn', 'sac', 'td3', 'random'],
        help='RL algorithm to use (default: ppo)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Path to pre-trained model'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    server = RLServer(
        host=args.host,
        port=args.port,
        algorithm=args.algorithm,
        model_path=args.model
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Received signal, shutting down...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server.start()


if __name__ == '__main__':
    main()