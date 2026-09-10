"""
Industrial UHF RFID Reader Driver (Python 3)
Compatible with Raspberry Pi (Linux), Windows, and macOS.
Communicates directly over RS232 / USB-Serial using the native wire protocol.
No vendor DLL, JNI, or Java dependencies required.
"""

import sys
import glob
import time
import serial
from typing import List, Optional, Dict, Any, Callable

class RFIDTag:
    def __init__(self, epc: str, length: int, timestamp: Optional[float] = None):
        self.epc = epc.upper()
        self.length = length
        self.timestamp = timestamp or time.time()
        self.read_count = 1

    @property
    def formatted_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

    def __repr__(self) -> str:
        return f"RFIDTag(EPC='{self.epc}', len={self.length}, time='{self.formatted_time}')"


class UHFReader:
    def __init__(
        self,
        port: str = "AUTO",
        baudrate: int = 115200,
        address: int = 0x00,
        timeout: float = 1.0
    ):
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    @staticmethod
    def calculate_crc(data: bytes) -> bytes:
        """CRC-16 CCITT (Poly: 0x8408, Init: 0xFFFF, Transmitted: LSB first, then MSB)."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc = crc >> 1
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    @staticmethod
    def auto_detect_port() -> Optional[str]:
        """Automatically scans and finds active USB-to-RS232 adapter ports."""
        if sys.platform.startswith("linux"):
            candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") + ["/dev/serial0", "/dev/ttyAMA0"]
        elif sys.platform.startswith("win"):
            candidates = [f"COM{i}" for i in range(1, 32)]
        elif sys.platform.startswith("darwin"):
            candidates = glob.glob("/dev/tty.usbserial*") + glob.glob("/dev/tty.usbmodem*")
        else:
            candidates = []

        for candidate in candidates:
            try:
                s = serial.Serial(candidate, baudrate=115200, timeout=0.3)
                s.close()
                return candidate
            except Exception:
                continue
        return None

    def connect(self) -> bool:
        """Opens serial port connection."""
        target_port = self.port
        if target_port == "AUTO" or not target_port:
            detected = self.auto_detect_port()
            if not detected:
                print("[ERROR] Auto-detect failed: No serial port found. Check USB connection.")
                return False
            target_port = detected
            self.port = target_port
            print(f"[INFO] Auto-detected RFID Reader port: {self.port}")

        try:
            self.ser = serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout)
            time.sleep(0.05)
            self.ser.reset_input_buffer()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to open port '{self.port}': {e}")
            return False

    def disconnect(self):
        """Closes the serial connection safely."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def send_frame(self, cmd: int, payload: bytes = b"") -> Optional[bytes]:
        """Builds packet frame, transmits over RS232, and reads response."""
        if not self.ser or not self.ser.is_open:
            return None

        # Request Frame: [Length, ComAdr, Cmd, ...Payload] + CRC_16
        length = len(payload) + 4
        frame_body = bytes([length, self.address, cmd]) + payload
        crc = self.calculate_crc(frame_body)
        full_frame = frame_body + crc

        try:
            self.ser.reset_input_buffer()
            self.ser.write(full_frame)

            # Read first byte (Length)
            header = self.ser.read(1)
            if not header:
                return None

            resp_len = header[0]
            if resp_len < 4 or resp_len > 255:
                return None

            # Read remaining payload + CRC
            remaining = self.ser.read(resp_len)
            full_resp = header + remaining

            if len(full_resp) < resp_len + 1:
                return None

            # Validate CRC
            calc_crc = self.calculate_crc(full_resp[:-2])
            if full_resp[-2:] != calc_crc:
                return None

            return full_resp
        except Exception as e:
            print(f"[WARN] Serial communication error: {e}")
            return None

    def get_reader_information(self) -> Optional[Dict[str, Any]]:
        """Queries reader model, firmware version, RF power, and scan limit."""
        resp = self.send_frame(0x21)
        if resp and len(resp) >= 12 and resp[3] == 0x00:
            return {
                "firmware_version": f"v{resp[4]}.{resp[5]:02d}",
                "reader_type": f"0x{resp[6]:02X}",
                "protocol": f"0x{resp[7]:02X}",
                "rf_power_dbm": resp[10],
                "scan_time_limit_ms": resp[11] * 100
            }
        return None

    def set_rf_power(self, power_dbm: int) -> bool:
        """Sets reader RF Output Power (0 to 30 dBm)."""
        if power_dbm < 0 or power_dbm > 30:
            raise ValueError("RF Power must be between 0 and 30 dBm")
        resp = self.send_frame(0x2F, bytes([power_dbm]))
        return bool(resp and len(resp) >= 4 and resp[3] == 0x00)

    def set_scan_time(self, scan_time_ms: int) -> bool:
        """Sets max scan duration per inventory round (in steps of 100ms, max 25500ms)."""
        val = max(1, min(255, scan_time_ms // 100))
        resp = self.send_frame(0x25, bytes([val]))
        return bool(resp and len(resp) >= 4 and resp[3] == 0x00)

    def buzzer_control(self, active_time_x10ms: int = 5, silent_time_x10ms: int = 5, count: int = 1) -> bool:
        """Triggers reader buzzer / LED indicator."""
        payload = bytes([active_time_x10ms, silent_time_x10ms, count])
        resp = self.send_frame(0x33, payload)
        return bool(resp and len(resp) >= 4 and resp[3] == 0x00)

    def inventory(self) -> List[RFIDTag]:
        """Performs EPC C1G2 inventory scan and parses all detected tag EPCs."""
        tags: List[RFIDTag] = []
        resp = self.send_frame(0x01)
        if not resp or len(resp) < 5:
            return tags

        status = resp[3]
        # Status 0x00 (Success), 0x01 (Return before finished), 0x02 (Scan time limit), 0x03, 0x04
        if status in [0x00, 0x01, 0x02, 0x03, 0x04] and len(resp) > 5:
            tag_count = resp[4]
            idx = 5
            now = time.time()
            for _ in range(tag_count):
                if idx < len(resp) - 2:
                    epc_len = resp[idx]
                    idx += 1
                    epc_bytes = resp[idx:idx + epc_len]
                    idx += epc_len
                    tags.append(RFIDTag(epc=epc_bytes.hex().upper(), length=epc_len, timestamp=now))
        return tags

    def continuous_scan(
        self,
        interval: float = 0.1,
        dedup_seconds: float = 2.0,
        callback: Optional[Callable[[RFIDTag], None]] = None
    ):
        """Continuous scanning generator yielding newly discovered RFID tags."""
        seen_tags: Dict[str, float] = {}

        while True:
            tags = self.inventory()
            now = time.time()

            # Clean expired tags from deduplication buffer
            seen_tags = {epc: t for epc, t in seen_tags.items() if now - t < dedup_seconds}

            for tag in tags:
                is_new = (tag.epc not in seen_tags)
                seen_tags[tag.epc] = now

                if is_new:
                    if callback:
                        callback(tag)
                    yield tag

            time.sleep(interval)
