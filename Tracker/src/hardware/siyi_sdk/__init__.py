"""
SIYI SDK - Main Interface

Unified SDK for SIYI gimbal camera control.
Combines all modules into a single easy-to-use interface.
"""

from .siyi_connection import SIYIConnection
from .siyi_camera_info import SIYICameraInfo
from .siyi_gimbal import SIYIGimbal
from .siyi_zoom import SIYIZoom
from .siyi_capture import SIYICapture


class SIYISDK:
    """
    Main SIYI SDK interface
    
    Provides unified access to all camera and gimbal functions:
    - Connection management
    - Camera information
    - Gimbal control
    - Zoom operations
    - Photo/video capture
    """
    
    def __init__(self, host: str = "192.168.144.25", port: int = 37260):
        """
        Initialize SIYI SDK
        
        Args:
            host: Camera IP address (default: 192.168.144.25)
            port: Camera TCP port (default: 37260)
        """
        self.connection = SIYIConnection(host, port)
        self.camera_info = SIYICameraInfo(self.connection)
        self.gimbal = SIYIGimbal(self.connection)
        self.zoom = SIYIZoom(self.connection)
        self.capture = SIYICapture(self.connection)
        
        self._connected = False
    
    def connect(self) -> bool:
        """
        Connect to the camera
        
        Returns:
            True if connection successful
        """
        self._connected = self.connection.connect()
        return self._connected
    
    def disconnect(self):
        """Disconnect from the camera"""
        self.connection.disconnect()
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to camera"""
        return self._connected and self.connection.connected
    
    # Camera Info Methods
    def get_hardware_id(self) -> str:
        """Get camera hardware ID"""
        return self.camera_info.get_hardware_id()
    
    def get_firmware_version(self) -> str:
        """Get camera firmware version"""
        return self.camera_info.get_firmware_version()
    
    # Gimbal Control Methods
    def center_gimbal(self) -> bool:
        """Center the gimbal"""
        return self.gimbal.center()
    
    def rotate_gimbal(self, yaw: int, pitch: int) -> bool:
        """
        Rotate gimbal with speed values
        
        Args:
            yaw: Yaw speed (-100 to 100)
            pitch: Pitch speed (-100 to 100)
        """
        return self.gimbal.rotate(yaw, pitch)
    
    def set_gimbal_angle(self, yaw: float, pitch: float) -> bool:
        """
        Set absolute gimbal angles
        
        Args:
            yaw: Yaw angle in degrees (-135 to 135)
            pitch: Pitch angle in degrees (-90 to 25)
        """
        return self.gimbal.control_angle(yaw, pitch)
    
    def set_lock_mode(self) -> bool:
        """Set gimbal to Lock mode"""
        return self.gimbal.set_mode_lock()
    
    def set_follow_mode(self) -> bool:
        """Set gimbal to Follow mode"""
        return self.gimbal.set_mode_follow()
    
    def set_fpv_mode(self) -> bool:
        """Set gimbal to FPV mode"""
        return self.gimbal.set_mode_fpv()
    
    def get_gimbal_status(self) -> dict:
        """Get gimbal status information"""
        return self.gimbal.get_status()
    
    def get_gimbal_attitude(self) -> dict:
        """Get gimbal attitude (yaw, pitch, roll)"""
        return self.gimbal.get_attitude()
    
    def get_working_mode(self) -> str:
        """Get current gimbal working mode"""
        return self.gimbal.get_working_mode()
    
    # Zoom Control Methods
    def zoom_in(self) -> bool:
        """Zoom in by one step"""
        return self.zoom.zoom_in()
    
    def zoom_out(self) -> bool:
        """Zoom out by one step"""
        return self.zoom.zoom_out()
    
    def manual_zoom_in(self) -> bool:
        """Manual zoom in"""
        return self.zoom.manual_zoom_in()
    
    def manual_zoom_out(self) -> bool:
        """Manual zoom out"""
        return self.zoom.manual_zoom_out()
    
    def set_zoom(self, zoom_level: float) -> bool:
        """
        Set absolute zoom level
        
        Args:
            zoom_level: Zoom multiplier (e.g., 1.0, 4.5, 10.0)
        """
        return self.zoom.set_absolute_zoom(zoom_level)
    
    def get_max_zoom(self) -> float:
        """Get maximum zoom value"""
        return self.zoom.get_max_zoom()
    
    def get_current_zoom(self) -> float:
        """Get current zoom value"""
        return self.zoom.get_current_zoom()
    
    # Capture Methods
    def take_picture(self) -> bool:
        """Take a picture"""
        return self.capture.take_picture()
    
    def record_video(self) -> bool:
        """Start/stop video recording"""
        return self.capture.record_video()
    
    def auto_focus(self) -> bool:
        """Trigger auto focus"""
        return self.capture.auto_focus()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


if __name__ == "__main__":
    # Demo usage
    import time
    
    print("=" * 60)
    print("SIYI SDK Demo")
    print("=" * 60)
    
    # Using context manager for automatic connection/disconnection
    with SIYISDK() as sdk:
        if sdk.is_connected():
            print("\n✓ Connected to camera\n")
            
            # Get camera info
            print("--- Camera Information ---")
            hw_id = sdk.get_hardware_id()
            fw_ver = sdk.get_firmware_version()
            time.sleep(1)
            
            # Gimbal control
            print("\n--- Gimbal Control ---")
            sdk.center_gimbal()
            time.sleep(2)
            
            sdk.rotate_gimbal(50, 30)
            time.sleep(2)
            
            sdk.center_gimbal()
            time.sleep(2)
            
            # Zoom control
            print("\n--- Zoom Control ---")
            current_zoom = sdk.get_current_zoom()
            time.sleep(1)
            
            sdk.zoom_in()
            time.sleep(1)
            
            sdk.zoom_out()
            time.sleep(1)
            
            # Capture
            print("\n--- Capture ---")
            sdk.auto_focus()
            time.sleep(1)
            
            sdk.take_picture()
            time.sleep(1)
            
            print("\n" + "=" * 60)
            print("✓ Demo complete")
            print("=" * 60)
        else:
            print("\n✗ Failed to connect to camera")
