# Intelbras Alarm Integration for Home Assistant

Control your Intelbras AMT alarm panels directly from Home Assistant using the native protocol!

## Features

🛡️ **Direct Control** - Arm/disarm your alarm system with instant status updates
🔌 **PGM Outputs** - Control programmable outputs (PGM 1-4) via switch entities  
📊 **Real-time Status** - Live monitoring of armed/disarmed state
🏠 **Local Network** - No cloud dependency, direct panel communication
🔒 **Native Protocol** - Direct communication using reverse-engineered 0xe7 protocol

## What you get

- **Alarm Control Panel**: Full arm/disarm control with status monitoring
- **Binary Sensors**: Connection status, alarm state, system problems
- **Switch Entities**: Control PGM outputs (programmable relays/outputs)
- **Sensor Entities**: System diagnostics and health monitoring

## Requirements

- Intelbras AMT panel (AMT 1016 NET tested, AMT 2018/2008 NET expected compatible)
- Panel connected to your local network with IP access
- Panel's hex password (4-6 digits, same as used in Android app)
- Home Assistant 2023.1.0 or newer

## Quick Setup

1. Add integration through HACS or manually
2. Enter your panel's IP address and password
3. Start automating your alarm system!

## Professional Integration

This integration uses the same native protocol as the official Intelbras Android app, providing direct and reliable communication with your alarm panel.

---

**Brazilian alarm control, automated! 🇧🇷**
