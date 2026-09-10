---
description: Development guidelines and quality standards for UHF RFID serial protocols and embedded drivers.
globs: ["**/*.py", "**/*.sh"]
---

# UHF RFID Serial Driver Development Guidelines

1. **Protocol Purity**: Use the reverse-engineered serial protocol directly in Python (`pyserial`). Do NOT introduce dependencies on Windows-only DLLs, C# binaries, or 32-bit JNI wrappers.
2. **Checksum Integrity**: All transmitted and received frames must be checked with CRC-16 CCITT (`0x8408` polynomial, `0xFFFF` init, LSB first).
3. **Cross-Platform Compatibility**: Use dynamic serial port resolution (`/dev/ttyUSB*` on Linux, `COM*` on Windows) instead of hardcoding OS-specific port names.
4. **Buffer Hygiene**: Always call `ser.reset_input_buffer()` before writing a command frame to prevent stale bytes from corrupting packet responses.
5. **Tag Deduplication**: Ensure inventory scanning loops implement a configurable deduplication window to avoid flooding downstream consumers with duplicate tag events.
