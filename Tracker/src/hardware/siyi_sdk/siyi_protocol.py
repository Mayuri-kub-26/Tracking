"""
SIYI SDK Protocol Handler

Implements the SIYI camera/gimbal communication protocol:
- Packet structure: STX (0x6655), CTRL, Data_len, SEQ, CMD_ID, DATA, CRC16
- CRC16 checksum calculation
- Packet building and parsing
- Sequence number management
"""

import struct
from typing import Optional, Tuple


class SIYIProtocol:
    """SIYI Protocol packet builder and parser"""
    
    # Protocol constants
    STX = 0x6655  # Starting mark (low byte first)
    CTRL_NEED_ACK = 0x00
    CTRL_ACK_PACK = 0x01
    
    def __init__(self):
        self.sequence = 0  # Frame sequence counter (0-65535)
    
    def _calculate_crc16(self, data: bytes) -> int:
        """
        Calculate CRC16 checksum for the data packet (CRC-16/XMODEM)
        
        Args:
            data: Complete packet data (without CRC16)
            
        Returns:
            CRC16 checksum value
        """
        crc = 0
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        return crc
    
    def _get_next_sequence(self) -> int:
        """Get next sequence number and increment counter"""
        seq = self.sequence
        self.sequence = (self.sequence + 1) % 65536  # Wrap around at 65535
        return seq
    
    def build_packet(self, cmd_id: int, data: bytes = b'', need_ack: bool = False) -> bytes:
        """
        Build a complete SIYI protocol packet
        
        Args:
            cmd_id: Command ID (1 byte)
            data: Data payload (optional)
            need_ack: Whether this packet needs acknowledgment
            
        Returns:
            Complete packet with CRC16 checksum
        """
        # CTRL byte: 0x01 for commands (ack_pack), 0x00 for requests (need_ack)
        ctrl = self.CTRL_NEED_ACK if need_ack else self.CTRL_ACK_PACK
        
        # Data length (low byte first)
        data_len = len(data)
        
        # Sequence number
        seq = self._get_next_sequence()
        
        # Build packet without CRC16
        packet = struct.pack(
            '<HBHHB',  # < = little-endian, H = uint16, B = uint8
            self.STX,   # Starting mark (2 bytes)
            ctrl,       # Control byte (1 byte)
            data_len,   # Data length (2 bytes)
            seq,        # Sequence (2 bytes)
            cmd_id      # Command ID (1 byte)
        )
        
        # Add data payload
        packet += data
        
        # Calculate and append CRC16 (low byte first)
        crc16 = self._calculate_crc16(packet)
        packet += struct.pack('<H', crc16)
        
        return packet
    
    def parse_packet(self, packet: bytes) -> Optional[dict]:
        """
        Parse a received SIYI protocol packet
        
        Args:
            packet: Raw packet bytes
            
        Returns:
            Dictionary with parsed fields or None if invalid
        """
        if len(packet) < 10:  # Minimum packet size
            return None
        
        # Extract header (8 bytes)
        try:
            stx, ctrl, data_len, seq, cmd_id = struct.unpack('<HBHHB', packet[:8])
        except struct.error:
            return None
        
        # Verify STX
        if stx != self.STX:
            return None
        
        # Extract data and CRC16
        expected_len = 8 + data_len + 2  # header + data + crc16
        if len(packet) < expected_len:
            return None
        
        data = packet[8:8+data_len]
        received_crc16 = struct.unpack('<H', packet[8+data_len:8+data_len+2])[0]
        
        # Verify CRC16
        calculated_crc16 = self._calculate_crc16(packet[:8+data_len])
        if received_crc16 != calculated_crc16:
            return None
        
        return {
            'ctrl': ctrl,
            'data_len': data_len,
            'seq': seq,
            'cmd_id': cmd_id,
            'data': data,
            'crc16': received_crc16
        }
    
    def packet_to_hex(self, packet: bytes) -> str:
        """Convert packet to hex string for debugging"""
        return ' '.join(f'{b:02x}' for b in packet)


# Command ID constants
class Commands:
    """SIYI SDK Command IDs"""
    HEARTBEAT = 0x00
    FIRMWARE_VERSION = 0x01
    HARDWARE_ID = 0x02
    AUTO_FOCUS = 0x04
    AUTO_FOCUS = 0x04
    MANUAL_ZOOM = 0x05 # Reverted to 0x05 per user confirmation
    # ZOOM_CONTROL = 0x05
    GIMBAL_ROTATION = 0x07
    CENTER = 0x08
    STATUS_INFO = 0x0A
    CAPTURE_MODE = 0x0C  # Used for photo, video, and gimbal modes
    ATTITUDE_DATA = 0x0D
    CONTROL_ANGLE = 0x0E
    ABSOLUTE_ZOOM = 0x0F
    MAX_ZOOM_VALUE = 0x16
    CURRENT_ZOOM_VALUE = 0x18
    WORKING_MODE = 0x19


if __name__ == "__main__":
    # Test the protocol with known packets
    protocol = SIYIProtocol()
    
    print("=== Testing SIYI Protocol ===\n")
    
    # Test 1: Heartbeat packet
    print("Test 1: TCP Heartbeat")
    heartbeat = protocol.build_packet(Commands.HEARTBEAT, b'\x00')
    print(f"Built: {protocol.packet_to_hex(heartbeat)}")
    print(f"Expected: 55 66 01 01 00 00 00 00 00 59 8b")
    print(f"Match: {protocol.packet_to_hex(heartbeat).upper() == '55 66 01 01 00 00 00 00 00 59 8B'}\n")
    
    # Test 2: Center command
    print("Test 2: Center Gimbal")
    center = protocol.build_packet(Commands.CENTER, b'\x01')
    print(f"Built: {protocol.packet_to_hex(center)}")
    print(f"Expected: 55 66 01 01 00 00 00 08 01 d1 12")
    print(f"Match: {protocol.packet_to_hex(center).upper() == '55 66 01 01 00 00 00 08 01 D1 12'}\n")
    
    # Test 3: Firmware version request
    print("Test 3: Firmware Version Request")
    fw_req = protocol.build_packet(Commands.FIRMWARE_VERSION, b'', need_ack=True)
    print(f"Built: {protocol.packet_to_hex(fw_req)}")
    print(f"Expected: 55 66 01 00 00 00 00 01 64 c4")
    print(f"Match: {protocol.packet_to_hex(fw_req).upper() == '55 66 01 00 00 00 00 01 64 C4'}\n")
    
    # Test 4: Parse a packet
    print("Test 4: Parse Packet")
    test_packet = bytes.fromhex('55 66 01 01 00 00 00 00 00 59 8b')
    parsed = protocol.parse_packet(test_packet)
    if parsed:
        print(f"Parsed successfully: CMD_ID={parsed['cmd_id']:02X}, SEQ={parsed['seq']}, DATA={parsed['data'].hex()}")
    else:
        print("Failed to parse packet")
