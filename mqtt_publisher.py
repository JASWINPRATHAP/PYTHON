#!/usr/bin/env python3
"""
RFID Tag MQTT Publisher for IoT / Home Assistant / ERP integration.
Reads tags from UHF Reader and publishes JSON events to an MQTT broker.
"""

import os
import sys
import json
import time
import argparse
from rfid_driver import UHFReader, RFIDTag

def main():
    parser = argparse.ArgumentParser(description="RFID Tag MQTT Publisher")
    parser.add_argument("--broker", default="localhost", help="MQTT Broker host (default: localhost)")
    parser.add_argument("--port", "-p", type=int, default=1883, help="MQTT Broker port (default: 1883)")
    parser.add_argument("--topic", default="rfid/tags", help="MQTT Topic (default: rfid/tags)")
    parser.add_argument("--serial-port", default="AUTO", help="RFID serial port (e.g. /dev/ttyUSB0)")
    parser.add_argument("--interval", type=float, default=0.1, help="Scan interval in seconds")
    parser.add_argument("--dedup", type=float, default=2.0, help="Deduplication window in seconds")
    args = parser.parse_args()

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[ERROR] paho-mqtt is required for MQTT publishing.")
        print("Run: pip install paho-mqtt")
        sys.exit(1)

    client = mqtt.Client()
    try:
        client.connect(args.broker, args.port, 60)
        client.loop_start()
        print(f"[OK] Connected to MQTT Broker at {args.broker}:{args.port}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MQTT broker: {e}")
        sys.exit(1)

    reader = UHFReader(port=args.serial_port)
    if not reader.connect():
        print("[ERROR] Could not connect to RFID reader.")
        sys.exit(1)

    print(f"[OK] RFID Reader connected on {reader.port}")
    print(f"Publishing newly scanned tags to topic '{args.topic}'...\n")

    def on_tag_scanned(tag: RFIDTag):
        payload = {
            "epc": tag.epc,
            "length": tag.length,
            "timestamp": tag.timestamp,
            "date_time": tag.formatted_time
        }
        json_msg = json.dumps(payload)
        client.publish(args.topic, json_msg)
        print(f"-> Published to {args.topic}: {json_msg}")

    try:
        for _ in reader.continuous_scan(interval=args.interval, dedup_seconds=args.dedup, callback=on_tag_scanned):
            pass
    except KeyboardInterrupt:
        print("\nStopping MQTT publisher...")
    finally:
        reader.disconnect()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
