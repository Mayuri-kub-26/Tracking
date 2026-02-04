"""
SIYI Zoom Control Module

Handles zoom operations:
- Incremental zoom (+/-)
- Absolute zoom positioning
- Manual zoom control
- Zoom value queries
"""

from .siyi_connection import SIYIConnection
from .siyi_protocol import Commands
import struct
import time


class SIYIZoom:
    """Zoom control operations"""
    
    def __init__(self, connection: SIYIConnection):
        """
        Initialize zoom control module
        
        Args:
            connection: Active SIYI connection
        """
        self.connection = connection
    
    def zoom_in(self) -> bool:
        """
        Start zooming in (Continuous)
        """
        print("\n→ Start zooming in...")
        # Manual says 1: Start zooming in
        result = self.connection.send_packet(Commands.MANUAL_ZOOM, b'\x01')
        if result:
            print("✓ Zoom in command sent")
        return result
    
    def zoom_out(self) -> bool:
        """
        Start zooming out (Continuous)
        """
        print("\n→ Start zooming out...")
        # Manual says -1 (0xFF): Start zooming out
        result = self.connection.send_packet(Commands.MANUAL_ZOOM, b'\xFF')
        if result:
            print("✓ Zoom out command sent")
        return result

    def stop_zoom(self) -> bool:
        """
        Stop zooming
        """
        print("\n→ Stop zooming...")
        # Manual says 0: Stop zooming
        result = self.connection.send_packet(Commands.MANUAL_ZOOM, b'\x00')
        if result:
            print("✓ Stop zoom command sent")
        return result
    
    # Deprecated manual_zoom_in/out if they were doing something different
    # But for now we just map them to the same logic or remove them.
    # We will keep them for compatibility but map them to the new logic.
    def manual_zoom_in(self) -> bool:
        return self.zoom_in()
    
    def manual_zoom_out(self) -> bool:
        return self.zoom_out()
    
    def set_absolute_zoom(self, zoom_level: float) -> bool:
        """
        Set absolute zoom level
        
        Args:
            zoom_level: Zoom multiplier (e.g., 1.0, 4.5, 10.0)
            
        Returns:
            True if command sent successfully
        """
        # Convert zoom level to appropriate format
        # Based on example: 4.5X = 04 05 (4 and 0.5)
        integer_part = int(zoom_level)
        decimal_part = int((zoom_level - integer_part) * 10)
        
        # Pack as 16 bytes with zoom data
        data = b'\x00' * 10  # Padding
        data += struct.pack('BB', integer_part, decimal_part)
        data += b'\x00' * 4  # More padding
        
        print(f"\n→ Setting absolute zoom to {zoom_level}X...")
        result = self.connection.send_packet(Commands.ABSOLUTE_ZOOM, data)
        if result:
            print(f"✓ Absolute zoom command sent ({zoom_level}X)")
        return result
    
    def get_max_zoom(self, timeout: float = 2.0) -> float:
        """
        Request maximum zoom value
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Maximum zoom value or 0.0 if failed
        """
        print("\n→ Requesting max zoom value...")
        
        if not self.connection.send_packet(Commands.MAX_ZOOM_VALUE, b'', need_ack=True):
            return 0.0
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.MAX_ZOOM_VALUE:
                if len(response['data']) >= 2:
                    # Parse zoom value (typically integer and decimal parts)
                    integer_part = response['data'][0]
                    decimal_part = response['data'][1] if len(response['data']) > 1 else 0
                    max_zoom = integer_part + (decimal_part / 10.0)
                    print(f"✓ Max zoom: {max_zoom}X")
                    return max_zoom
                else:
                    print(f"✓ Max zoom (raw): {response['data'].hex()}")
                    return 0.0
            time.sleep(0.1)
        
        print("✗ No response received")
        return 0.0
    
    def get_current_zoom(self, timeout: float = 2.0) -> float:
        """
        Request current zoom value
        
        Args:
            timeout: Response timeout in seconds
            
        Returns:
            Current zoom value or 0.0 if failed
        """
        print("\n→ Requesting current zoom value...")
        
        if not self.connection.send_packet(Commands.CURRENT_ZOOM_VALUE, b'', need_ack=True):
            return 0.0
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.connection.receive_packet(timeout=0.5)
            if response and response['cmd_id'] == Commands.CURRENT_ZOOM_VALUE:
                if len(response['data']) >= 2:
                    # Parse zoom value (typically integer and decimal parts)
                    integer_part = response['data'][0]
                    decimal_part = response['data'][1] if len(response['data']) > 1 else 0
                    current_zoom = integer_part + (decimal_part / 10.0)
                    print(f"✓ Current zoom: {current_zoom}X")
                    return current_zoom
                else:
                    print(f"✓ Current zoom (raw): {response['data'].hex()}")
                    return 0.0
            time.sleep(0.1)
        
        print("✗ No response received")
        return 0.0


if __name__ == "__main__":
    # Test zoom control
    print("=" * 50)
    print("SIYI Zoom Control Test")
    print("=" * 50)
    
    conn = SIYIConnection()
    
    if conn.connect():
        zoom = SIYIZoom(conn)
        
        # Get current zoom
        current = zoom.get_current_zoom()
        time.sleep(1)
        
        # Get max zoom
        max_zoom = zoom.get_max_zoom()
        time.sleep(1)
        
        # Test zoom in
        zoom.zoom_in()
        time.sleep(2)
        
        # Test zoom out
        zoom.zoom_out()
        time.sleep(2)
        
        # Test absolute zoom
        zoom.set_absolute_zoom(4.5)
        time.sleep(2)
        
        conn.disconnect()
        
        print("\n" + "=" * 50)
        print("✓ Zoom control test complete")
        print("=" * 50)
    else:
        print("\n✗ Connection failed")
