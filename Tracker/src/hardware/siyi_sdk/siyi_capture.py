"""
SIYI Camera Capture Module

Handles photo and video capture:
- Take picture
- Record video
- Auto focus
"""

from .siyi_connection import SIYIConnection
from .siyi_protocol import Commands


class SIYICapture:
    """Camera capture operations"""
    
    def __init__(self, connection: SIYIConnection):
        """
        Initialize capture module
        
        Args:
            connection: Active SIYI connection
        """
        self.connection = connection
    
    def take_picture(self) -> bool:
        """
        Take a picture
        
        Returns:
            True if command sent successfully
        """
        print("\n→ Taking picture...")
        result = self.connection.send_packet(Commands.CAPTURE_MODE, b'\x00')
        if result:
            print("✓ Picture capture command sent")
        return result
    
    def record_video(self) -> bool:
        """
        Start/stop video recording
        
        Returns:
            True if command sent successfully
        """
        print("\n→ Toggling video recording...")
        result = self.connection.send_packet(Commands.CAPTURE_MODE, b'\x02')
        if result:
            print("✓ Video recording command sent")
        return result
    
    def auto_focus(self) -> bool:
        """
        Trigger auto focus
        
        Returns:
            True if command sent successfully
        """
        print("\n→ Triggering auto focus...")
        result = self.connection.send_packet(Commands.AUTO_FOCUS, b'\x01')
        if result:
            print("✓ Auto focus command sent")
        return result


if __name__ == "__main__":
    # Test capture operations
    import time
    
    print("=" * 50)
    print("SIYI Capture Test")
    print("=" * 50)
    
    conn = SIYIConnection()
    
    if conn.connect():
        capture = SIYICapture(conn)
        
        # Test auto focus
        capture.auto_focus()
        time.sleep(2)
        
        # Test take picture
        capture.take_picture()
        time.sleep(2)
        
        # Test video recording (start)
        print("\nStarting video recording...")
        capture.record_video()
        time.sleep(3)
        
        # Test video recording (stop)
        print("\nStopping video recording...")
        capture.record_video()
        time.sleep(1)
        
        conn.disconnect()
        
        print("\n" + "=" * 50)
        print("✓ Capture test complete")
        print("=" * 50)
    else:
        print("\n✗ Connection failed")
