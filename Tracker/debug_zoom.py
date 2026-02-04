
import sys
import time
import socket
import struct

# Helper to build packet manually
def build_packet(cmd_id, data):
    STX = 0x6655
    CTRL = 1 # ACK_PACK
    seq = 0
    data_len = len(data)
    
    packet = struct.pack('<HBHHB', STX, CTRL, data_len, seq, cmd_id)
    packet += data
    
    # Simple CRC
    crc = 0
    for byte in packet:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
            
    packet += struct.pack('<H', crc)
    return packet

def test_connection_and_zoom(ip, port):
    print(f"--- Testing Connection to {ip}:{port} ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    
    try:
        sock.connect((ip, port))
        print("✓ TCP Connection Established")
    except Exception as e:
        print(f"✗ Connection Failed: {e}")
        return

    # Try Manual Zoom with CMD 0x05
    print("\nSending CMD 0x05 (Manual Zoom/Auto Focus)...")
    pkt5 = build_packet(0x05, b'\x01')
    try:
        sock.send(pkt5)
        resp = sock.recv(1024)
        if resp:
            print(f"Response to 0x05: {resp.hex()}")
        else:
            print("No response to 0x05")
    except Exception as e:
        print(f"Error sending 0x05: {e}")
        
    # Send Stop (0x05)
    sock.send(build_packet(0x05, b'\x00'))
    time.sleep(0.5)

    # Try Manual Zoom with CMD 0x06
    print("\nSending CMD 0x06 (Legacy/Other Manual Zoom)...")
    pkt6 = build_packet(0x06, b'\x01')
    try:
        sock.send(pkt6)
        resp = sock.recv(1024)
        if resp:
            print(f"Response to 0x06: {resp.hex()}")
        else:
            print("No response to 0x06")
    except Exception as e:
        print(f"Error sending 0x06: {e}")

    # Send Stop (0x06)
    sock.send(build_packet(0x06, b'\x00'))
    
    sock.close()

if __name__ == "__main__":
    # Test configured IP
    test_connection_and_zoom("192.168.145.25", 37260)
    
    print("\n" + "="*30 + "\n")
    
    # Test standard IP just in case
    test_connection_and_zoom("192.168.144.25", 37260)
