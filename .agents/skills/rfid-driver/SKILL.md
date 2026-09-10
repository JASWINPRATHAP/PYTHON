---
name: rfid-driver
description: >-
  Expert instructions and protocol reference for communicating with Industrial UHF RFID
  readers over RS232 / USB-Serial, including frame encoding/decoding, CRC-16 CCITT calculations,
  EPC Class 1 Gen 2 inventory commands, and hardware settings.
---

# Industrial UHF RFID Reader Driver Skill

This skill provides full technical specifications, packet formats, and procedural runbooks for integrating with industrial UHF RFID readers over RS232 / Serial.

---

## 1. Serial Protocol Specification

- **Baud Rate**: 115,200 bps (default)
- **Data Format**: 8-N-1 (8 Data bits, No Parity, 1 Stop bit)
- **Default Device Address**: `0x00` (Broadcast: `0xFF`)
- **Checksum**: CRC-16 CCITT (`Poly: 0x8408`, `Init: 0xFFFF`, Transmitted `LSB first, then MSB`)

---

## 2. Frame Structure

### Request Frame (TX)
```text
[ Length (1B) | ComAdr (1B) | Command (1B) | Payload (0..N B) | CRC_LSB (1B) | CRC_MSB (1B) ]
```
- `Length` = `len(Payload) + 4`

### Response Frame (RX)
```text
[ Length (1B) | ComAdr (1B) | Command (1B) | Status (1B) | Data (0..M B) | CRC_LSB (1B) | CRC_MSB (1B) ]
```

---

## 3. Standard Command Opcodes

| Command | Opcode | Request Example | Description |
| :--- | :--- | :--- | :--- |
| **Inventory_G2** | `0x01` | `[0x04, 0x00, 0x01, 0xDB, 0x4B]` | Scans RF field for EPC C1G2 tags |
| **GetReaderInfo** | `0x21` | `[0x04, 0x00, 0x21, 0xD9, 0x6A]` | Returns firmware version, RF power, scan time |
| **SetPowerDbm** | `0x2F` | `[0x05, 0x00, 0x2F, Power, CRC_L, CRC_H]` | Configures RF power (0-30 dBm) |
| **WriteScanTime**| `0x25` | `[0x05, 0x00, 0x25, Units, CRC_L, CRC_H]` | Configures max scan time ($N \times 100\text{ms}$) |
| **Buzzer/LED** | `0x33` | `[0x07, 0x00, 0x33, Act, Sil, Cnt, CRC_L, CRC_H]` | Triggers reader beep / LED indicator |

---

## 4. CRC-16 CCITT Python Implementation

```python
def calculate_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc = crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])
```
