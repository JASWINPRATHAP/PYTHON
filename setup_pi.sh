#!/bin/bash
# =======================================================
# Automated Setup Script for Raspberry Pi UHF RFID Reader
# =======================================================

echo "======================================================="
echo "   Setting up UHF RFID Reader on Raspberry Pi          "
echo "======================================================="

# 1. Add current user to dialout group for serial access
echo "[1/3] Adding $USER to 'dialout' group..."
sudo usermod -a -G dialout $USER

# 2. Install Python serial dependencies
echo "[2/3] Installing Python serial requirements..."
sudo apt update -y
sudo apt install -y python3-serial python3-pip

if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt
fi

# 3. Check for connected USB serial devices
echo "[3/3] Checking connected USB serial devices..."
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "Note: No /dev/ttyUSB device currently plugged in. Plug in your USB-to-RS232 adapter."

echo "======================================================="
echo "Setup complete! Run the live scanner with:"
echo "    python3 live_inventory.py"
echo "======================================================="
