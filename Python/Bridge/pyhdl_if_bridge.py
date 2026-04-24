"""
PyHDL-IF Bridge Module
Provides 2-way communication between SystemVerilog UVM testbench and Python RL modules
Using PyHDL-IF for HDL-HLS-HVL bridging without DPI-C or c-based intermediaries

Author: AI Assistant
Date: 2026-04-24
"""

import socket
import struct
import json
import threading
import time
import queue
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PyHDL-IF-Bridge')


class MessageType(Enum):
    """Message types for bridge communication"""
    STIMULUS = "STIMULUS"          # RL -> UVM: Generate stimulus
    RESPONSE = "RESPONSE"          # UVM -> RL: DUT response
    STATUS = "STATUS"               # Status updates
    CONFIG = "CONFIG"              # Configuration data
    COVERAGE = "COVERAGE"           # Coverage data
    REWARD = "REWARD"               # RL reward signal
    ACTION = "ACTION"               # RL action selection
    TERMINATE = "TERMINATE"         # End simulation
    HEARTBEAT = "HEARTBEAT"         # Keep-alive


class MessagePriority(Enum):
    """Message priority levels"""
    HIGH = 3
    NORMAL = 2
    LOW = 1


@dataclass
class Transaction:
    """Base transaction class for bridge communication"""
    msg_type: MessageType
    timestamp: float = field(default_factory=time.time)
    priority: MessagePriority = MessagePriority.NORMAL
    transaction_id: str = field(default_factory=lambda: f"TXN_{int(time.time()*1000000)}")
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_bytes(self) -> bytes:
        """Serialize transaction to bytes"""
        data = {
            'msg_type': self.msg_type.value,
            'timestamp': self.timestamp,
            'priority': self.priority.value,
            'transaction_id': self.transaction_id,
            'payload': self.payload
        }
        json_str = json.dumps(data)
        return json_str.encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Transaction':
        """Deserialize transaction from bytes"""
        json_str = data.decode('utf-8')
        data = json.loads(json_str)
        return cls(
            msg_type=MessageType(data['msg_type']),
            timestamp=data['timestamp'],
            priority=MessagePriority(data['priority']),
            transaction_id=data['transaction_id'],
            payload=data['payload']
        )


class BridgeTimeoutError(Exception):
    """Raised when bridge operation times out"""
    pass


class BridgeConnectionError(Exception):
    """Raised when bridge connection fails"""
    pass


class PyHDLIFBridge:
    """
    2-Way Bridge for HDL/HLS/HVL communication using PyHDL-IF patterns
    
    This bridge enables Python RL agents to communicate with SystemVerilog UVM
    testbenches through TCP/IP sockets. It implements:
    - Bidirectional communication (Python <-> UVM)
    - Message queuing with priority support
    - Transaction logging and tracing
    - Automatic reconnection handling
    - Heartbeat monitoring for connection health
    - Timeout handling with configurable thresholds
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5555,
        timeout: float = 5.0,
        max_retries: int = 3,
        heartbeat_interval: float = 1.0,
        enable_logging: bool = True
    ):
        """
        Initialize PyHDL-IF Bridge
        
        Args:
            host: Hostname for socket connection
            port: Port number for socket connection
            timeout: Timeout for socket operations (seconds)
            max_retries: Maximum reconnection attempts
            heartbeat_interval: Heartbeat check interval (seconds)
            enable_logging: Enable detailed logging
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.heartbeat_interval = heartbeat_interval
        
        # Connection state
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._running = False
        
        # Message queues
        self._send_queue: queue.Queue = queue.PriorityQueue()
        self._recv_queue: queue.Queue = queue.Queue()
        self._response_handlers: Dict[str, Callable] = {}
        self._pending_requests: Dict[str, queue.Queue] = {}
        
        # Threading
        self._send_thread: Optional[threading.Thread] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Statistics
        self._stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0,
            'timeouts': 0,
            'start_time': time.time()
        }
        
        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        logger.info(f"PyHDL-IF Bridge initialized for {host}:{port}")
    
    def connect(self) -> bool:
        """
        Establish connection to UVM testbench
        
        Returns:
            True if connection successful
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Connection attempt {attempt + 1}/{self.max_retries}")
                
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.settimeout(self.timeout)
                self._socket.connect((self.host, self.port))
                
                self._connected = True
                self._running = True
                
                # Start communication threads
                self._start_threads()
                
                logger.info(f"Successfully connected to {self.host}:{self.port}")
                
                if self._on_connect:
                    self._executor.submit(self._on_connect)
                
                return True
                
            except socket.error as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                self._stats['errors'] += 1
                
                if attempt < self.max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to connect after {self.max_retries} attempts")
                    if self._on_error:
                        self._executor.submit(self._on_error, e)
                    raise BridgeConnectionError(f"Cannot connect to {self.host}:{self.port}")
        
        return False
    
    def disconnect(self):
        """Gracefully disconnect from UVM testbench"""
        logger.info("Disconnecting from UVM testbench...")
        
        self._running = False
        
        # Stop threads
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=2.0)
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=2.0)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        
        # Close socket
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.warning(f"Error closing socket: {e}")
        
        self._connected = False
        
        if self._on_disconnect:
            self._executor.submit(self._on_disconnect)
        
        logger.info("Disconnected successfully")
    
    def _start_threads(self):
        """Start communication threads"""
        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()
        
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        
        logger.info("Communication threads started")
    
    def _send_loop(self):
        """Background thread for sending messages"""
        logger.info("Send thread started")
        
        while self._running and self._connected:
            try:
                if not self._send_queue.empty():
                    priority, txn = self._send_queue.get(timeout=0.1)
                    
                    if txn.msg_type == MessageType.TERMINATE:
                        logger.info("Termination message received, stopping send thread")
                        break
                    
                    self._send_message(txn)
                    self._stats['messages_sent'] += 1
                else:
                    time.sleep(0.001)  # Prevent busy waiting
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in send loop: {e}")
                self._stats['errors'] += 1
    
    def _recv_loop(self):
        """Background thread for receiving messages"""
        logger.info("Receive thread started")
        
        while self._running and self._connected:
            try:
                data = self._recv_message()
                
                if data:
                    txn = Transaction.from_bytes(data)
                    self._handle_received_message(txn)
                    self._stats['messages_received'] += 1
                else:
                    time.sleep(0.001)
                    
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                self._stats['errors'] += 1
    
    def _heartbeat_loop(self):
        """Background thread for heartbeat monitoring"""
        logger.info("Heartbeat thread started")
        
        while self._running and self._connected:
            try:
                heartbeat = Transaction(
                    msg_type=MessageType.HEARTBEAT,
                    payload={'timestamp': time.time()}
                )
                self._send_message(heartbeat)
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                if self._on_error:
                    self._executor.submit(self._on_error, e)
    
    def _send_message(self, txn: Transaction):
        """Send a message over the socket"""
        try:
            data = txn.to_bytes()
            length = len(data)
            
            # Send length prefix (4 bytes) + message
            header = struct.pack('!I', length)
            self._socket.sendall(header + data)
            
            logger.debug(f"Sent {txn.msg_type.value} transaction: {txn.transaction_id}")
            
        except socket.error as e:
            logger.error(f"Error sending message: {e}")
            self._stats['errors'] += 1
            self._connected = False
    
    def _recv_message(self) -> Optional[bytes]:
        """Receive a message from the socket"""
        try:
            # Receive length prefix
            header = self._socket.recv(4)
            if not header:
                return None
            
            length = struct.unpack('!I', header)[0]
            
            # Receive message data
            data = b''
            while len(data) < length:
                chunk = self._socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            
            return data
            
        except socket.timeout:
            return None
        except socket.error as e:
            logger.error(f"Error receiving message: {e}")
            return None
    
    def _handle_received_message(self, txn: Transaction):
        """Handle received message based on type"""
        logger.debug(f"Received {txn.msg_type.value} transaction: {txn.transaction_id}")
        
        # Check for pending request handlers
        if txn.transaction_id in self._pending_requests:
            self._pending_requests[txn.transaction_id].put(txn)
        
        # Add to general queue
        self._recv_queue.put(txn)
        
        # Call registered handler if exists
        if txn.msg_type in self._response_handlers:
            self._executor.submit(self._response_handlers[txn.msg_type], txn)
    
    def send(self, msg_type: MessageType, payload: Dict[str, Any],
             priority: MessagePriority = MessagePriority.NORMAL,
             wait_response: bool = False,
             response_timeout: Optional[float] = None) -> Optional[Transaction]:
        """
        Send a transaction and optionally wait for response
        
        Args:
            msg_type: Type of message
            payload: Message payload data
            priority: Message priority
            wait_response: Wait for response
            response_timeout: Timeout for response
            
        Returns:
            Response transaction if wait_response=True, None otherwise
        """
        if not self._connected:
            raise BridgeConnectionError("Not connected to UVM testbench")
        
        txn = Transaction(
            msg_type=msg_type,
            payload=payload,
            priority=priority
        )
        
        self._send_queue.put((priority.value, txn))
        
        if wait_response:
            response_q = queue.Queue()
            self._pending_requests[txn.transaction_id] = response_q
            
            try:
                timeout = response_timeout or self.timeout
                response = response_q.get(timeout=timeout)
                del self._pending_requests[txn.transaction_id]
                return response
            except queue.Empty:
                self._stats['timeouts'] += 1
                raise BridgeTimeoutError(f"Timeout waiting for response to {txn.transaction_id}")
        
        return None
    
    def recv(self, timeout: Optional[float] = None) -> Optional[Transaction]:
        """
        Receive a transaction from the queue
        
        Args:
            timeout: Maximum time to wait for message
            
        Returns:
            Transaction if available, None otherwise
        """
        try:
            if timeout:
                return self._recv_queue.get(timeout=timeout)
            else:
                return self._recv_queue.get_nowait()
        except queue.Empty:
            return None
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a callback handler for specific message type"""
        self._response_handlers[msg_type] = handler
        logger.info(f"Registered handler for {msg_type.value}")
    
    def set_connect_callback(self, callback: Callable):
        """Set callback for connection events"""
        self._on_connect = callback
    
    def set_disconnect_callback(self, callback: Callable):
        """Set callback for disconnection events"""
        self._on_disconnect = callback
    
    def set_error_callback(self, callback: Callable):
        """Set callback for error events"""
        self._on_error = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics"""
        stats = self._stats.copy()
        stats['connected'] = self._connected
        stats['uptime'] = time.time() - stats['start_time']
        stats['pending_requests'] = len(self._pending_requests)
        stats['send_queue_size'] = self._send_queue.qsize()
        stats['recv_queue_size'] = self._recv_queue.qsize()
        return stats
    
    @property
    def is_connected(self) -> bool:
        """Check if bridge is connected"""
        return self._connected


class ALUBridgeProtocol:
    """
    ALU-specific bridge protocol extending PyHDL-IF patterns
    Handles ALU verification transactions with proper handshaking
    """
    
    def __init__(self, bridge: PyHDLIFBridge):
        self.bridge = bridge
        self._coverage_data = {}
        self._transaction_history = []
        self._max_history = 10000
    
    def send_stimulus(self, a: int, b: int, op_code: int, 
                      c_in: int = 0, reset: int = 0,
                      wait_response: bool = True,
                      timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Send ALU stimulus and optionally wait for response
        
        Args:
            a: Input A (8-bit)
            b: Input B (8-bit)
            op_code: Operation code (4-bit, 0-5)
            c_in: Carry input (default 0)
            reset: Reset signal (default 0)
            wait_response: Wait for DUT response
            timeout: Response timeout
            
        Returns:
            Response data if wait_response=True
        """
        payload = {
            'A': a,
            'B': b,
            'op_code': op_code,
            'C_in': c_in,
            'Reset': reset,
            'timestamp': time.time()
        }
        
        response = self.bridge.send(
            msg_type=MessageType.STIMULUS,
            payload=payload,
            wait_response=wait_response,
            response_timeout=timeout
        )
        
        if response:
            self._add_to_history('STIMULUS', payload, response.payload)
            return response.payload
        return None
    
    def receive_coverage(self) -> Dict[str, Any]:
        """Receive coverage data from UVM"""
        try:
            txn = self.bridge.recv(timeout=0.1)
            if txn and txn.msg_type == MessageType.COVERAGE:
                self._coverage_data = txn.payload
                return txn.payload
        except queue.Empty:
            pass
        return self._coverage_data
    
    def send_reward(self, reward: float, coverage_increase: float = 0.0):
        """Send RL reward signal to UVM"""
        payload = {
            'reward': reward,
            'coverage_increase': coverage_increase,
            'timestamp': time.time()
        }
        
        self.bridge.send(
            msg_type=MessageType.REWARD,
            payload=payload,
            priority=MessagePriority.HIGH
        )
    
    def request_action(self, coverage_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Request RL action selection based on current coverage state"""
        response = self.bridge.send(
            msg_type=MessageType.ACTION,
            payload={'coverage_state': coverage_state},
            wait_response=True,
            response_timeout=2.0
        )
        
        if response:
            return response.payload
        return None
    
    def _add_to_history(self, direction: str, request: Dict, response: Dict):
        """Add transaction to history"""
        self._transaction_history.append({
            'direction': direction,
            'request': request,
            'response': response,
            'timestamp': time.time()
        })
        
        if len(self._transaction_history) > self._max_history:
            self._transaction_history.pop(0)
    
    def get_transaction_history(self) -> list:
        """Get transaction history"""
        return self._transaction_history
    
    def get_coverage_data(self) -> Dict[str, Any]:
        """Get current coverage data"""
        return self._coverage_data


def create_server_socket(host: str, port: int, backlog: int = 5) -> socket.socket:
    """
    Create a server socket for UVM side communication
    
    Args:
        host: Host to bind to
        port: Port to listen on
        backlog: Connection backlog
        
    Returns:
        Configured server socket
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(backlog)
    server.settimeout(1.0)  # Allow periodic checks
    return server


class UVMBridgeServer:
    """
    Server-side bridge for UVM testbench connection
    Used when UVM testbench acts as server (passive mode)
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5555):
        self.host = host
        self.port = port
        self.server: Optional[socket.socket] = None
        self.client: Optional[socket.socket] = None
        self._running = False
    
    def start(self, timeout: float = 30.0):
        """Start server and wait for connection"""
        self.server = create_server_socket(self.host, self.port)
        logger.info(f"Server listening on {self.host}:{self.port}")
        
        start_time = time.time()
        while self._running is False:
            try:
                self.client, addr = self.server.accept()
                logger.info(f"Client connected from {addr}")
                self._running = True
                break
            except socket.timeout:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Connection timeout")
    
    def stop(self):
        """Stop server"""
        self._running = False
        if self.client:
            self.client.close()
        if self.server:
            self.server.close()
        logger.info("Server stopped")