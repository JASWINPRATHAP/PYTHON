---
name: raspberry-pi-deployment
description: >-
  Workflows and best practices for configuring, deploying, and running serial IoT devices
  and RFID readers on Raspberry Pi Linux environments.
---

# Raspberry Pi Serial IoT Deployment Skill

This skill documents standard procedures for deploying Python serial applications on Raspberry Pi OS.

---

## 1. Serial Port Permissions
Linux requires membership in the `dialout` group to access `/dev/ttyUSB*` and `/dev/ttyACM*` without root privileges.

```bash
sudo usermod -a -G dialout $USER
```

---

## 2. Port Detection
Identify USB serial adapters using:
```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```
or inspecting kernel events:
```bash
dmesg | grep -i tty
```

---

## 3. Systemd Service Setup for Continuous Background Execution

1. Create `/etc/systemd/system/rfid.service`:
```ini
[Unit]
Description=UHF RFID Reader Live Scanner
After=network.target

[Service]
Type=simple
User=algo2
WorkingDirectory=/home/algo2/rfidtest/PYTHON
ExecStart=/usr/bin/python3 live_inventory.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

2. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rfid.service
sudo systemctl start rfid.service
```
