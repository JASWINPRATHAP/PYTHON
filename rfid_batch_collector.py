#!/usr/bin/env python3
"""
=============================================================================
   ALL-IN-ONE UHF RFID SCANNER & BATCH COLLECTOR FOR RASPBERRY PI / LINUX
=============================================================================
- Pure Python (No DLLs / No Java)
- Fast scanning (sets reader scan duration to 200ms)
- Auto-detects serial port (/dev/ttyUSB0, COM*, etc.)
- Continuous inventory scanning with full packet debugging
- Deduplicates and tracks Unique EPC IDs, Read Counts, First & Last Seen Times
- Batches and displays structured data periodically (Ready for DB insertion)
=============================================================================
"""

import sys
import glob
import time
import serial
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
PORT = "AUTO"             # "AUTO" or "/dev/ttyUSB0", "COM2", etc.
BAUDRATE = 115200         # Reader baudrate
READER_ADDR = 0x00        # Reader address (0x00)
RF_POWER_DBM = 30         # RF Output Power (0 - 30 dBm, 30 = Max range)
SCAN_TIME_MS = 200        # Reader hardware RF scan duration (in ms, e.g. 100, 200, 500)
BATCH_INTERVAL_SEC = 5.0  # Time window (seconds) to display batch summary
DEBUG_RAW_PACKETS = False # Set True to see raw TX/RX hex frames


# ==========================================
# 📡 SERIAL & PROTOCOL DRIVER
# ==========================================
def calculate_crc(data: bytes) -> bytes:
    """CRC-16 CCITT (Poly: 0x8408, Init: 0xFFFF, LSB first)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc = crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def auto_detect_port() -> str:
    """Automatically finds connected USB-to-RS232 adapter."""
    if sys.platform.startswith("linux"):
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") + ["/dev/serial0"]
    elif sys.platform.startswith("win"):
        candidates = [f"COM{i}" for i in range(1, 32)]
    else:
        candidates = glob.glob("/dev/tty.usbserial*")

    for port_name in candidates:
        try:
            s = serial.Serial(port_name, baudrate=BAUDRATE, timeout=0.3)
            s.close()
            return port_name
        except Exception:
            continue
    return None


def send_command(ser: serial.Serial, cmd: int, payload: bytes = b"", wait_sec: float = 0.3) -> bytes:
    """Sends packet frame and reads response."""
    length = len(payload) + 4
    msg = bytes([length, READER_ADDR, cmd]) + payload
    pkt = msg + calculate_crc(msg)

    if DEBUG_RAW_PACKETS:
        print(f"  [TX] {pkt.hex().upper()}")

    ser.reset_input_buffer()
    ser.write(pkt)

    # Allow reader time to scan and respond
    time.sleep(wait_sec)

    # Read response
    header = ser.read(1)
    if not header:
        # Fallback: check if bytes in buffer
        if ser.in_waiting > 0:
            header = ser.read(1)
        else:
            return None

    resp_len = header[0]
    if resp_len < 4 or resp_len > 255:
        return None

    remaining = ser.read(resp_len)
    full_resp = header + remaining

    if DEBUG_RAW_PACKETS:
        print(f"  [RX] {full_resp.hex().upper()} ({len(full_resp)} bytes)")

    if len(full_resp) < resp_len + 1:
        return None

    # Validate CRC
    calc_crc = calculate_crc(full_resp[:-2])
    if full_resp[-2:] != calc_crc:
        return None

    return full_resp


def get_reader_info(ser: serial.Serial):
    """Fetches reader firmware and hardware parameters."""
    resp = send_command(ser, 0x21, wait_sec=0.1)
    if resp and len(resp) >= 12 and resp[3] == 0x00:
        return {
            "firmware": f"v{resp[4]}.{resp[5]:02d}",
            "power": resp[10],
            "scan_time": resp[11] * 100
        }
    return None


def set_rf_power(ser: serial.Serial, power_dbm: int):
    """Sets RF Output Power (0-30 dBm)."""
    resp = send_command(ser, 0x2F, bytes([power_dbm]), wait_sec=0.1)
    return bool(resp and len(resp) >= 4 and resp[3] == 0x00)


def set_scan_time(ser: serial.Serial, scan_time_ms: int):
    """Sets RF scan time limit (100ms units: 1 = 100ms, 2 = 200ms, etc.)."""
    units = max(1, min(255, scan_time_ms // 100))
    resp = send_command(ser, 0x25, bytes([units]), wait_sec=0.1)
    return bool(resp and len(resp) >= 4 and resp[3] == 0x00)


def scan_inventory(ser: serial.Serial):
    """Performs one EPC Gen2 scan and parses all detected tag EPCs."""
    epc_list = []
    # Wait appropriate time for the configured scan duration (e.g. 0.25s for 200ms scan)
    wait_time = max(0.2, (SCAN_TIME_MS / 1000.0) + 0.05)
    resp = send_command(ser, 0x01, wait_sec=wait_time)
    
    if not resp or len(resp) < 5:
        return epc_list

    status = resp[3]
    # Status codes indicating tag discovery: 0x00, 0x01 (Early return), 0x02 (Scan limit), 0x03, 0x04
    if status in [0x00, 0x01, 0x02, 0x03, 0x04] and len(resp) > 5:
        tag_count = resp[4]
        idx = 5
        for _ in range(tag_count):
            if idx < len(resp) - 2:
                epc_len = resp[idx]
                idx += 1
                epc_bytes = resp[idx:idx + epc_len]
                idx += epc_len
                epc_list.append((epc_bytes.hex().upper(), epc_len))
    return epc_list


# ==========================================
# 🚀 MAIN APPLICATION LOGIC
# ==========================================
def main():
    print("=" * 70)
    print("      UHF RFID LIVE SCANNER & UNIQUE TAG BATCH COLLECTOR       ")
    print("=" * 70)

    # 1. Resolve Serial Port
    target_port = PORT
    if target_port == "AUTO":
        target_port = auto_detect_port()
        if not target_port:
            print("[ERROR] No serial port found. Check USB connection to RFID Reader.")
            sys.exit(1)
        print(f"[INFO] Auto-detected Serial Port: {target_port}")

    # 2. Connect to Reader with sufficient timeout
    try:
        ser = serial.Serial(target_port, baudrate=BAUDRATE, timeout=2.0)
        time.sleep(0.1)
    except Exception as e:
        print(f"[ERROR] Could not open port {target_port}: {e}")
        sys.exit(1)

    print(f"[SUCCESS] Connected to RFID Reader on {target_port}")

    # 3. Optimize Hardware Settings for Fast, Sensitive Scanning
    set_scan_time(ser, SCAN_TIME_MS)
    set_rf_power(ser, RF_POWER_DBM)

    info = get_reader_info(ser)
    if info:
        print(f" Firmware : {info['firmware']} | RF Power: {info['power']} dBm | Scan Limit: {info['scan_time']} ms")

    print("=" * 70)
    print(f" Ready! Scanning continuously (Batch window: {BATCH_INTERVAL_SEC}s)...")
    print(" 👉 Place RFID tags in front of antenna.")
    print("=" * 70 + "\n")

    batch_tags = {}
    batch_start_time = time.time()
    batch_number = 1
    total_lifetime_unique_tags = set()
    total_scan_rounds = 0

    try:
        while True:
            total_scan_rounds += 1
            tags = scan_inventory(ser)
            now = datetime.now()

            for epc, epc_len in tags:
                if epc not in batch_tags:
                    batch_tags[epc] = {
                        "length": epc_len,
                        "count": 1,
                        "first_seen": now,
                        "last_seen": now
                    }
                    total_lifetime_unique_tags.add(epc)
                    print(f"  ⚡ [TAG DETECTED] EPC: {epc} ({epc_len} bytes) at {now.strftime('%H:%M:%S')}")
                else:
                    batch_tags[epc]["count"] += 1
                    batch_tags[epc]["last_seen"] = now

            # Flush Batch after interval
            elapsed = time.time() - batch_start_time
            if elapsed >= BATCH_INTERVAL_SEC:
                print("\n" + "#" * 70)
                print(f" 📦 BATCH #{batch_number} SUMMARY | Unique Tags: {len(batch_tags)} | Total Scans: {total_scan_rounds}")
                print(f" Window Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("#" * 70)

                if batch_tags:
                    print(f"{'NO':<4} | {'EPC IDENTIFIER':<28} | {'COUNT':<6} | {'FIRST SEEN':<10} | {'LAST SEEN':<10}")
                    print("-" * 75)
                    for i, (epc, data) in enumerate(batch_tags.items(), 1):
                        f_seen = data["first_seen"].strftime("%H:%M:%S")
                        l_seen = data["last_seen"].strftime("%H:%M:%S")
                        print(f"#{i:<3} | {epc:<28} | {data['count']:<6} | {f_seen:<10} | {l_seen:<10}")
                    
                    print("-" * 75)
                    print(f" [DB READY] {len(batch_tags)} unique records prepared for database insertion.")
                else:
                    print(" (No tags detected in this 5-second window - bring tag closer to antenna)")

                print("#" * 70 + "\n")

                # Reset for next window
                batch_tags.clear()
                batch_start_time = time.time()
                batch_number += 1

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print(f"[STOPPED] Total Unique Tags Seen: {len(total_lifetime_unique_tags)}")
        print("=" * 70)
    finally:
        ser.close()
        print("Serial port closed cleanly.")


if __name__ == "__main__":
    main()
