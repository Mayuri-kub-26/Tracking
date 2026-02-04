"""
SIYI Gimbal Control Module

Handles gimbal control operations:
- Center gimbal
- Gimbal rotation (pitch/yaw control)
- Control angle (absolute positioning)
- Gimbal modes (Lock, Follow, FPV)
- Status and attitude data
"""

from .siyi_connection import SIYIConnection
from .siyi_protocol import Commands
import struct
import time


class SIYIGimbal:
    """Gimbal control and positioning"""
    
    def __init__(self, connection: SIYIConnection):
        """
        Initialize gimbal control module
        
        Args:
            connection: Active SIYI connection
        """
        self.connection = connection
    
    def center(self) -> bool:
        """
        Center the gimbal
        
        Returns:
            True if command sent successfully
        """
        print("\n>> Centering gimbal...")
        result = self.connection.send_packet(Commands.CENTER, b'\x01')
        if result:
            print("[OK] Center command sent")
        return result
    
    def rotate(self, yaw: int, pitch: int) -> bool:
        """
        Control gimbal rotation with speed values
        
        Args:
            yaw: Yaw speed (-100 to 100, negative=left, positive=right)
            pitch: Pitch speed (-100 to 100, negative=down, positive=up)
            
        Returns:
            True if command sent successfully
        """
        # Clamp values to valid range
        yaw = max(-100, min(100, yaw))
        pitch = max(-100, min(100, pitch))
        
        # Pack as signed bytes (int8_t)
        data = struct.pack('bb', yaw, pitch)
        
        print(f"\n>> Rotating gimbal (yaw={yaw}, pitch={pitch})...")
        result = self.connection.send_packet(Commands.GIMBAL_ROTATION, data)
        if result:
            print("[OK] Rotation command sent")
        return result
    
    def control_angle(self, yaw: float, pitch: float) -> bool:
        """
        Set absolute gimbal angles
        
        Args:
            yaw: Yaw angle in degrees (-135 to 135)
            pitch: Pitch angle in degrees (-90 to 25)
            
        Returns:
            True if command sent successfully
        """
        # Convert angles to int16 (degrees * 10)
        yaw_int = int(yaw * 10)
        pitch_int = int(pitch * 10)
        
        # Pack as little-endian int16
        data = struct.pack('<hh', yaw_int, pitch_int)
        
        print(f"\n>> Setting gimbal angle (yaw={yaw}°, pitch={pitch}°)...")
        result = self.connection.send_packet(Commands.CONTROL_ANGLE, data)
        if result:
            print("[OK] Angle control command sent")
        return result
    
    def set_mode_lock(self) -> bool:
        """
        Set gimbal to Lock mode
        
        Returns:
            True if command sent successfully
        """
        print("\n>> Setting Lock mode...")
        result = self.connection.send_packet(Commands.CAPTURE_MODE, b'\x03')
        if result:
            print("[OK] Lock mode command sent")
        return result
    
    def set_mode_follow(self) -> bool:
        """
        Set gimbal to Follow mode
        
        Returns:
            True if command sent successfully
        """
        print("\n>> Setting Follow mode...")
        result = self.connection.send_packet(Commands.CAPTURE_MODE, b'\x04')
        if result:
            print("[OK] Follow mode command sent")
        return result
    
    def set_mode_fpv(self) -> bool:
        """
        Set gimbal to FPV mode
        
        Returns:
            True if command sent successfully
        """
        print("\n>> Setting FPV mode...")
        result = self.connection.send_packet(Commands.CAPTURE_MODE, b'\x05')
        if result:
            print("[OK] FPV mode command sent")
        return result
    
    def get_status(self, timeout: float = 2.0) -> dict:
        """
        Request gimbal status information
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Dictionary with status data or empty dict if failed
        """
        print("\n>> Requesting gimbal status...")
        
        if not self.connection.send_packet(Commands.STATUS_INFO, b'', need_ack=True):
            return {}
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.STATUS_INFO:
                print(f"[OK] Status received: {response['data'].hex()}")
                return {'raw_data': response['data']}
            time.sleep(0.1)
        
        print("[ERROR] No response received")
        return {}
    
    def get_attitude(self, timeout: float = 2.0) -> dict:
        """
        Request gimbal attitude data
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Dictionary with attitude data (yaw, pitch, roll) or empty dict if failed
        """
        print("\n>> Requesting gimbal attitude...")
        
        if not self.connection.send_packet(Commands.ATTITUDE_DATA, b'', need_ack=True):
            return {}
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.ATTITUDE_DATA:
                # Parse attitude data (typically int16 values for yaw, pitch, roll)
                if len(response['data']) >= 6:
                    yaw, pitch, roll = struct.unpack('<hhh', response['data'][:6])
                    # Convert from int16 to degrees (divide by 10)
                    attitude = {
                        'yaw': yaw / 10.0,
                        'pitch': pitch / 10.0,
                        'roll': roll / 10.0
                    }
                    print(f"[OK] Attitude: yaw={attitude['yaw']}°, pitch={attitude['pitch']}°, roll={attitude['roll']}°")
                    return attitude
                else:
                    print(f"[OK] Attitude (raw): {response['data'].hex()}")
                    return {'raw_data': response['data']}
            time.sleep(0.1)
        
        print("[ERROR] No response received")
        return {}
    
    def get_working_mode(self, timeout: float = 2.0) -> str:
        """
        Request gimbal working mode
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Working mode string or empty string if failed
        """
        print("\n>> Requesting working mode...")
        
        if not self.connection.send_packet(Commands.WORKING_MODE, b'', need_ack=True):
            return ""
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.WORKING_MODE:
                if len(response['data']) > 0:
                    mode_byte = response['data'][0]
                    modes = {0x03: "Lock", 0x04: "Follow", 0x05: "FPV"}
                    mode = modes.get(mode_byte, f"Unknown (0x{mode_byte:02X})")
                    print(f"[OK] Working mode: {mode}")
                    return mode
                else:
                    print(f"[OK] Working mode (raw): {response['data'].hex()}")
                    return response['data'].hex()
            time.sleep(0.1)
        
        print("[ERROR] No response received")
        return ""


if __name__ == "__main__":
    # Test gimbal control
    print("=" * 50)
    print("SIYI Gimbal Control Test")
    print("=" * 50)
    
    conn = SIYIConnection()
    
    if conn.connect():
        gimbal = SIYIGimbal(conn)
        
        # Test center
        gimbal.center()
        time.sleep(2)
        
        # Test rotation
        gimbal.rotate(50, 50)
        time.sleep(2)
        
        # Test center again
        gimbal.center()
        time.sleep(2)
        
        # Test modes
        gimbal.set_mode_follow()
        time.sleep(1)
        
        # Test status
        gimbal.get_status()
        time.sleep(1)
        
        # Test attitude
        gimbal.get_attitude()
        time.sleep(1)
        
        conn.disconnect()
        
        print("\n" + "=" * 50)
        print("[OK] Gimbal control test complete")
        print("=" * 50)
    else:
        print("\n[ERROR] Connection failed")
