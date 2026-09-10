#!/usr/bin/env python3
"""
Live RFID Tag Scanner CLI Application
Supports CLI arguments, config.json, auto-port detection, live table, and CSV output.
"""

import os
import sys
import json
import time
import argparse
import csv
from rfid_driver import UHFReader, RFIDTag

def load_config(config_path: str = "config.json") -> dict:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Could not parse {config_path}: {e}")
    return {}

def main():
    parser = argparse.ArgumentParser(description="Industrial UHF RFID Reader Live Scanner")
    parser.add_argument("--port", "-p", default=None, help="Serial port (e.g. /dev/ttyUSB0, COM2, or AUTO)")
    parser.add_argument("--baud", "-b", type=int, default=None, help="Baud rate (default: 115200)")
    parser.add_argument("--power", type=int, default=None, help="RF Power in dBm (0 to 30)")
    parser.add_argument("--interval", "-i", type=float, default=None, help="Scan loop interval in seconds (default: 0.1)")
    parser.add_argument("--dedup", "-d", type=float, default=None, help="Deduplication window in seconds (default: 2.0)")
    parser.add_argument("--config", "-c", default="config.json", help="Path to config.json file")
    parser.add_argument("--csv", default=None, help="Path to export scanned tags as CSV")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Precedence: CLI Argument -> config.json -> Fallback Default
    serial_cfg = cfg.get("serial", {})
    reader_cfg = cfg.get("reader", {})
    scanner_cfg = cfg.get("scanner", {})
    output_cfg = cfg.get("output", {})

    port = args.port or serial_cfg.get("port", "AUTO")
    baud = args.baud or serial_cfg.get("baudrate", 115200)
    addr = serial_cfg.get("address", 0x00)
    power_dbm = args.power or reader_cfg.get("rf_power_dbm", 30)
    scan_interval = args.interval or scanner_cfg.get("scan_interval_seconds", 0.1)
    dedup_window = args.dedup or scanner_cfg.get("deduplication_window_seconds", 2.0)
    beep_on_tag = reader_cfg.get("beep_on_tag", False)
    csv_file = args.csv or (output_cfg.get("csv_filepath") if output_cfg.get("save_csv") else None)

    print("=" * 65)
    print("        INDUSTRIAL UHF RFID READER - LIVE TAG SCANNER            ")
    print("=" * 65)
    print(f" Target Port   : {port}")
    print(f" Baud Rate     : {baud} bps")
    print(f" Target Address: 0x{addr:02X}")
    print(f" Dedup Window  : {dedup_window}s | Scan Interval: {scan_interval}s")
    if csv_file:
        print(f" CSV Logging   : Enabled -> {csv_file}")
    print("=" * 65)

    reader = UHFReader(port=port, baudrate=baud, address=addr)
    if not reader.connect():
        print("\n[ERROR] Connection failed. Please check:")
        print(" 1. Is the USB/RS232 cable connected?")
        print(" 2. On Linux / Pi: Run 'ls /dev/ttyUSB*' to verify device name.")
        print(" 3. Serial permissions: sudo usermod -a -G dialout $USER")
        sys.exit(1)

    print(f"[SUCCESS] Connected to reader on port: {reader.port}")

    # Query reader info
    info = reader.get_reader_information()
    if info:
        print("\n--- Reader Hardware Configuration ---")
        print(f" Firmware Version : {info['firmware_version']}")
        print(f" Reader Type Code : {info['reader_type']}")
        print(f" Current RF Power : {info['rf_power_dbm']} dBm")
        print(f" Scan Time Limit  : {info['scan_time_limit_ms']} ms")
    
    # Optionally configure RF Power if specified
    if power_dbm:
        if reader.set_rf_power(power_dbm):
            print(f" [OK] RF Power set to: {power_dbm} dBm")

    # Safe CSV File Initialization
    csv_writer_func = None
    if csv_file:
        try:
            csv_path = os.path.abspath(csv_file)
            csv_dir = os.path.dirname(csv_path)
            if csv_dir and not os.path.exists(csv_dir):
                os.makedirs(csv_dir, exist_ok=True)

            file_exists = os.path.isfile(csv_path)
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists or os.path.getsize(csv_path) == 0:
                    writer.writerow(["Timestamp", "Date_Time", "EPC", "Length_Bytes"])

            def append_csv(t: RFIDTag):
                try:
                    with open(csv_path, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([int(t.timestamp), t.formatted_time, t.epc, t.length])
                except Exception as ex:
                    print(f"\n[WARN] Failed to write to CSV: {ex}")

            csv_writer_func = append_csv
            print(f"[INFO] CSV logging active at: {csv_path}")
        except Exception as e:
            print(f"[WARN] Could not initialize CSV file '{csv_file}': {e}. Continuing without CSV logging.")
            csv_writer_func = None

    print("\nStarting live EPC inventory scan... Press Ctrl+C to stop.\n")
    print(f"{'INDEX':<6} | {'TIMESTAMP':<19} | {'BYTES':<5} | {'EPC CODE'}")
    print("-" * 65)

    total_scans = 0
    tag_count = 0
    seen_db = {}

    try:
        while True:
            total_scans += 1
            tags = reader.inventory()
            now = time.time()

            # Clean up deduplication cache
            seen_db = {epc: t for epc, t in seen_db.items() if now - t < dedup_window}

            for tag in tags:
                if tag.epc not in seen_db:
                    seen_db[tag.epc] = now
                    tag_count += 1
                    
                    print(f"#{tag_count:<5} | {tag.formatted_time} | {tag.length:<5} | {tag.epc}")

                    if beep_on_tag:
                        try:
                            reader.buzzer_control(5, 5, 1)
                        except Exception:
                            pass

                    if csv_writer_func:
                        csv_writer_func(tag)

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 65)
        print(f"[STOPPED] Total Scan Cycles: {total_scans} | Unique Tag Reads: {tag_count}")
        print("=" * 65)
    finally:
        reader.disconnect()
        print("Reader disconnected cleanly.")

if __name__ == "__main__":
    main()
