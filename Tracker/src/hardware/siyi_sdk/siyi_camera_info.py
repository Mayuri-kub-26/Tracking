"""
SIYI Camera Information Module

Handles camera information retrieval:
- Hardware ID
- Firmware Version
"""

from .siyi_connection import SIYIConnection
from .siyi_protocol import Commands
import time


class SIYICameraInfo:
    """Camera information retrieval"""
    
    def __init__(self, connection: SIYIConnection):
        """
        Initialize camera info module
        
        Args:
            connection: Active SIYI connection
        """
        self.connection = connection
    
    def get_hardware_id(self, timeout: float = 2.0) -> str:
        """
        Request camera hardware ID
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Hardware ID string or empty string if failed
        """
        print("\n→ Requesting Hardware ID...")
        
        # Send request
        if not self.connection.send_packet(Commands.HARDWARE_ID, b'', need_ack=True):
            return ""
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.HARDWARE_ID:
                # Parse hardware ID from response data
                hw_id = response['data'].decode('utf-8', errors='ignore').strip('\x00')
                print(f"✓ Hardware ID: {hw_id}")
                return hw_id
            time.sleep(0.1)
        
        print("✗ No response received")
        return ""
    
    def get_firmware_version(self, timeout: float = 2.0) -> str:
        """
        Request camera firmware version
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Firmware version string or empty string if failed
        """
        print("\n→ Requesting Firmware Version...")
        
        # Send request
        if not self.connection.send_packet(Commands.FIRMWARE_VERSION, b'', need_ack=True):
            return ""
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.FIRMWARE_VERSION:
                # Parse firmware version from response data
                # Typically format: major.minor.patch
                if len(response['data']) >= 3:
                    major = response['data'][0]
                    minor = response['data'][1]
                    patch = response['data'][2]
                    version = f"{major}.{minor}.{patch}"
                    print(f"✓ Firmware Version: {version}")
                    return version
                else:
                    fw_ver = response['data'].hex()
                    print(f"✓ Firmware Version (raw): {fw_ver}")
                    return fw_ver
            time.sleep(0.1)
        
        print("✗ No response received")
        return ""


if __name__ == "__main__":
    # Test camera info retrieval
    print("=" * 50)
    print("SIYI Camera Info Test")
    print("=" * 50)
    
    conn = SIYIConnection()
    
    if conn.connect():
        camera_info = SIYICameraInfo(conn)
        
        # Get hardware ID
        hw_id = camera_info.get_hardware_id()
        
        # Get firmware version
        fw_ver = camera_info.get_firmware_version()
        
        time.sleep(2)
        conn.disconnect()
        
        print("\n" + "=" * 50)
        if hw_id or fw_ver:
            print("✓ Camera info test PASSED")
        else:
            print("✗ Camera info test FAILED")
        print("=" * 50)
    else:
        print("\n✗ Connection failed")
