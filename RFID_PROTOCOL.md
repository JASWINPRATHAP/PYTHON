# Industrial UHF RFID Reader RS232 Wire Protocol Specification

## 1. Physical & Serial Communication Layer

- **Physical Interface**: RS232 / USB-to-UART Bridge (COM port, 3.3V/5V logic or DB9 RS232)
- **Default Baud Rate**: `115,200 bps` (Configurable: 9600, 19200, 38400, 56000, 57600, 115200)
- **Data Format**: 8 Data Bits, 1 Stop Bit, No Parity (`8-N-1`)
- **Flow Control**: None (Hardware flow control disabled)
- **Default Reader Address**: `0x00` (Broadcast Address: `0xFF`)

---

## 2. Packet Frame Format

Every frame transmitted over RS232 follows a consistent structure:

### Master to Reader Request Frame (TX)
```text
+----------+----------+----------+-----------------------+----------+----------+
|  Length  | ComAdr   | Command  |  Parameters / Payload  |  CRC_LSB |  CRC_MSB |
|  (1 byte)| (1 byte) | (1 byte) |     (0..N bytes)      |  (1 byte)|  (1 byte)|
+----------+----------+----------+-----------------------+----------+----------+
```

- **Length** (1 byte): Total number of bytes in frame including `Length`, `ComAdr`, `Command`, `Payload`, and 2 CRC bytes.
  $$\text{Length} = 1 (\text{Length}) + 1 (\text{ComAdr}) + 1 (\text{Cmd}) + N (\text{Payload}) + 2 (\text{CRC}) - 1 = N + 4$$
- **ComAdr** (1 byte): Target reader address (`0x00` default, `0xFF` broadcast).
- **Command** (1 byte): Operation opcode.
- **Payload** (N bytes): Command arguments (optional).
- **CRC-16** (2 bytes): 16-bit CRC calculated over all preceding bytes (`[Length, ComAdr, Cmd, ...Payload]`), transmitted **LSB first**, followed by **MSB**.

### Reader to Master Response Frame (RX)
```text
+----------+----------+----------+----------+-----------------------+----------+----------+
|  Length  | ComAdr   | Command  |  Status  |  Response Data/Tags   |  CRC_LSB |  CRC_MSB |
|  (1 byte)| (1 byte) | (1 byte) | (1 byte) |     (0..M bytes)      |  (1 byte)|  (1 byte)|
+----------+----------+----------+----------+-----------------------+----------+----------+
```

- **Status** (1 byte): Execution status code:
  - `0x00`: Success
  - `0x01`: Return before inventory finished (valid tags returned)
  - `0x02`: Inventory scan-time overflow (valid tags returned)
  - `0x03`: More data available in buffer
  - `0x04`: Reader module MCU buffer full
  - `0xFB`: No tag operable (no tag in RF field)
  - `0x30`: Communication error
  - `0x31`: CRC error
  - `0xFE`: Illegal command / invalid parameter

---

## 3. CRC-16 Checksum Algorithm

- **Algorithm**: CRC-16 CCITT (ISO 3309 / ISO 14443 standard)
- **Polynomial**: `0x8408` (Reversed `0x1021`, $x^{16} + x^{12} + x^5 + 1$)
- **Initial Value**: `0xFFFF`
- **Byte Order**: LSB first, then MSB.

### Python Implementation
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

---

## 4. Confirmed Command Reference

### 4.1 GetReaderInformation (Opcode `0x21`)
Queries reader firmware version, reader type, RF power, and scan limit.

- **Request (5 bytes)**:
  `[0x04, 0x00, 0x21, 0xD9, 0x6A]` (Addr `0x00`)
- **Response (14 bytes)**:
  `[0x0D, 0x00, 0x21, 0x00, MajorVer, MinorVer, ReaderType, Protocol, FreqHigh, FreqLow, PowerDbm, ScanTime, CRC_L, CRC_H]`
  - *Example Observed from Device*: `0D 00 21 00 03 3F 09 03 4E 00 1E 0A 83 F0`
  - Firmware: `v3.63` (`03 3F`)
  - Type: `0x09`
  - Protocol: `0x03` (EPC C1G2 & ISO 18000-6B)
  - Power: `30 dBm` (`0x1E`)
  - Scan Time Limit: `1000 ms` (`0x0A` = 10 * 100ms)

---

### 4.2 Inventory EPC Class 1 Gen 2 (Opcode `0x01`)
Scans RF field for UHF RFID EPC tags.

- **Request (5 bytes)**:
  `[0x04, 0x00, 0x01, 0xDB, 0x4B]`
- **Response**:
  `[Length, ComAdr, 0x01, Status, CardNum, Tag1_EPCLen, Tag1_EPC..., CRC_L, CRC_H]`
  - If tags detected: `Status = 0x01` / `0x02` / `0x00`, `CardNum` = Tag Count.
  - If no tags in field: `Status = 0xFB` or `0xFE`.

---

### 4.3 GetWorkModeParameter (Opcode `0x36`)
- **Request (5 bytes)**: `[0x04, 0x00, 0x36, 0xE7, 0x0E]`
- **Response (18 bytes)**: `11 00 36 00 00 1E 0A 0F 01 02 01 05 05 00 08 05 5D FE`
  - `Status = 0x00`, `WorkMode = 0x00` (Answer / Response Mode).
