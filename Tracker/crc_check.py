
import struct

def calculate_crc16(data: bytes) -> int:
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

# Manual Zoom 1
# 55 66 01 01 00 00 00 06 01 de 31
packet_1_hex = "55 66 01 01 00 00 00 06 01"
packet_1 = bytes.fromhex(packet_1_hex)
crc_1 = calculate_crc16(packet_1)
print(f"Packet 1 (CMD 06) CRC: {crc_1:04x} (Expected: 31de or de31)")

# Manual Zoom -1
# 55 66 01 01 00 00 00 06 ff 0f 3f
packet_2_hex = "55 66 01 01 00 00 00 06 ff"
packet_2 = bytes.fromhex(packet_2_hex)
crc_2 = calculate_crc16(packet_2)
print(f"Packet 2 (CMD 06) CRC: {crc_2:04x} (Expected: 3f0f or 0f3f)")

# Check CMD 05 just in case
packet_3_hex = "55 66 01 01 00 00 00 05 01"
packet_3 = bytes.fromhex(packet_3_hex)
crc_3 = calculate_crc16(packet_3)
print(f"Packet 3 (CMD 05) CRC: {crc_3:04x}")
