# Standalone Python UHF RFID Driver & Scanner

A pure Python 3 driver, scanner, and IoT publisher for Industrial UHF RFID Readers over RS232 / USB-Serial.

- **Zero Vendor DLL / JNI / Java Dependencies** (Runs natively on Linux, Raspberry Pi, Windows, and macOS)
- **Automatic Port Discovery** (Autodetects `/dev/ttyUSB0`, `/dev/ttyACM0` on Linux, `COM*` on Windows)
- **Centralized Configuration** via `config.json` or CLI flags
- **Live Real-time Inventory** with EPC display, deduplication, and CSV output
- **MQTT Event Streaming** for IoT / ERP / Home Assistant integration

---

## 📁 Directory Structure

```text
PYTHON/
├── rfid_driver.py       # Core standalone serial driver & CRC-16 protocol implementation
├── live_inventory.py    # Terminal CLI live inventory scanner with auto-port detection
├── mqtt_publisher.py    # MQTT publisher streaming RFID tag events as JSON
├── config.json          # Configuration file (port, baud, RF power, scan interval)
├── setup_pi.sh          # One-step Raspberry Pi setup script
├── rfid.service         # Systemd service template for 24/7 background execution
├── requirements.txt     # Python requirements (pyserial)
├── RFID_PROTOCOL.md     # Reverse-engineered wire protocol specification
└── README.md            # Documentation
```

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```
*(On Raspberry Pi, you can simply run `./setup_pi.sh`)*

---

### 2. Run Live Inventory Scanner
```bash
python3 live_inventory.py
```
* Automatically detects `/dev/ttyUSB0` or `COM*`.
* Scans for EPC Class 1 Gen 2 tags in real-time.

---

## ⚙️ Configuration

### Via `config.json`
```json
{
  "serial": {
    "port": "AUTO",
    "baudrate": 115200,
    "address": 0
  },
  "reader": {
    "rf_power_dbm": 30,
    "beep_on_tag": false
  },
  "scanner": {
    "scan_interval_seconds": 0.1,
    "deduplication_window_seconds": 2.0
  },
  "output": {
    "save_csv": true,
    "csv_filepath": "scanned_tags.csv"
  }
}
```

### Via Command-Line Flags
```bash
# Custom port:
python3 live_inventory.py --port /dev/ttyUSB0

# Set RF Power (0-30 dBm):
python3 live_inventory.py --power 28

# Save tags to CSV:
python3 live_inventory.py --csv scans.csv

# Custom scan interval & deduplication time:
python3 live_inventory.py --interval 0.05 --dedup 1.0
```

---

## 📡 MQTT IoT Integration
```bash
python3 mqtt_publisher.py --broker 192.168.1.100 --topic rfid/tags
```
Tags are published as JSON payloads:
```json
{
  "epc": "E28011700000020B80B5DE50",
  "length": 12,
  "timestamp": 1725275000.12,
  "date_time": "2026-09-10 09:15:00"
}
```

---

## 🔄 Run as Systemd Service (Raspberry Pi Auto-Start)
```bash
sudo cp rfid.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rfid.service
sudo systemctl start rfid.service

# View live scan logs:
journalctl -u rfid.service -f
```
