"""
SIYI SDK Connection Manager

Handles TCP connection to SIYI camera/gimbal:
- TCP client connection
- Heartbeat management
- Send/receive packet handling
- Auto-reconnect support
"""

import socket
import threading
import time
from typing import Optional, Callable
from .siyi_protocol import SIYIProtocol, Commands


class SIYIConnection:
    """Manages TCP connection to SIYI camera/gimbal"""
    
    def __init__(self, host: str = "192.168.144.25", port: int = 37260):
        """
        Initialize connection manager
        
        Args:
            host: Camera IP address
            port: Camera TCP port
        """
        self.host = host
        self.port = port
        self.protocol = SIYIProtocol()
        self.socket: Optional[socket.socket] = None
        self.connected = False
        
        # Heartbeat management
        self.heartbeat_interval = 1.0  # seconds
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.heartbeat_running = False
        
        # Response callback
        self.response_callback: Optional[Callable] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.receive_running = False
        
    def connect(self) -> bool:
        """
        Establish TCP connection to camera
        
        Returns:
            True if connected successfully
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5 second timeout
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"[OK] Connected to {self.host}:{self.port}")
            
            # Start receive thread
            self._start_receive_thread()
            
            # Start heartbeat
            self.start_heartbeat()
            
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close connection and stop heartbeat"""
        self.stop_heartbeat()
        self._stop_receive_thread()
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        print("[OK] Disconnected")
    
    def send_packet(self, cmd_id: int, data: bytes = b'', need_ack: bool = False) -> bool:
        """
        Send a packet to the camera
        
        Args:
            cmd_id: Command ID
            data: Data payload
            need_ack: Whether packet needs acknowledgment
            
        Returns:
            True if sent successfully
        """
        if not self.connected or not self.socket:
            print("[ERROR] Not connected")
            return False
        
        try:
            packet = self.protocol.build_packet(cmd_id, data, need_ack)
            self.socket.sendall(packet)
            print(f">> Sent: {self.protocol.packet_to_hex(packet)}")
            return True
        except Exception as e:
            print(f"[ERROR] Send failed: {e}")
            return False
    
    def receive_packet(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Receive a packet from the camera
        
        Args:
            timeout: Receive timeout in seconds
            
        Returns:
            Parsed packet dictionary or None
        """
        if not self.connected or not self.socket:
            return None
        
        try:
            self.socket.settimeout(timeout)
            data = self.socket.recv(1024)
            if data:
                parsed = self.protocol.parse_packet(data)
                if parsed:
                    print(f"<< Received: CMD_ID={parsed['cmd_id']:02X}, DATA={parsed['data'].hex()}")
                return parsed
        except socket.timeout:
            return None
        except Exception as e:
            print(f"[ERROR] Receive failed: {e}")
            return None
    
    def _receive_loop(self):
        """Background thread for receiving packets"""
        while self.receive_running and self.connected:
            try:
                if self.socket:
                    self.socket.settimeout(0.5)
                    data = self.socket.recv(1024)
                    if data:
                        parsed = self.protocol.parse_packet(data)
                        if parsed and self.response_callback:
                            self.response_callback(parsed)
            except socket.timeout:
                continue
            except Exception as e:
                if self.receive_running:
                    print(f"[ERROR] Receive loop error: {e}")
                break
    
    def _start_receive_thread(self):
        """Start background receive thread"""
        if not self.receive_running:
            self.receive_running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
    
    def _stop_receive_thread(self):
        """Stop background receive thread"""
        self.receive_running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
            self.receive_thread = None
    
    def _heartbeat_loop(self):
        """Background thread for sending heartbeat packets"""
        while self.heartbeat_running and self.connected:
            self.send_packet(Commands.HEARTBEAT, b'\x00')
            time.sleep(self.heartbeat_interval)
    
    def start_heartbeat(self):
        """Start sending heartbeat packets"""
        if not self.heartbeat_running:
            self.heartbeat_running = True
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            print("[OK] Heartbeat started")
    
    def stop_heartbeat(self):
        """Stop sending heartbeat packets"""
        self.heartbeat_running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2.0)
            self.heartbeat_thread = None
            print("[OK] Heartbeat stopped")
    
    def set_response_callback(self, callback: Callable):
        """Set callback function for received packets"""
        self.response_callback = callback


if __name__ == "__main__":
    # Test connection
    print("=== Testing SIYI Connection ===\n")
    
    conn = SIYIConnection()
    
    print("Attempting to connect...")
    if conn.connect():
        print("Connection successful!")
        print("Heartbeat running for 5 seconds...")
        time.sleep(5)
        conn.disconnect()
    else:
        print("Connection failed. Make sure camera is accessible at 192.168.144.25:37260")
