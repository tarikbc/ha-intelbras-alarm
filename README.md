# Intelbras Alarm Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Project Maintenance][maintenance-shield]][user_profile]

<img src="https://brands.home-assistant.io/intelbras_alarm/icon.png" alt="PPA Contatto" width="200" align="right">

A custom Home Assistant integration for Intelbras AMT alarm systems using the native 0xe7 protocol.

> **✅ Installation Note**: This integration can be installed through HACS (Home Assistant Community Store) or manually. It provides direct communication with your alarm panel using the same protocol as the official Android app.

## Features

- **Direct Control**: Arm/disarm your alarm system with immediate status updates
- **Real-time Status**: Live monitoring of armed/disarmed state with instant feedback
- **PGM Output Control**: Control programmable outputs (PGM 1-4) through switch entities
- **System Monitoring**: Binary sensors for connection status, alarm state, and system problems
- **Native Protocol**: Direct communication using reverse-engineered 0xe7 protocol (same as Android app)
- **Local Network**: No cloud dependency, direct panel communication over TCP
- **Professional Testing**: Extensively tested with real AMT 1016 NET hardware
- **Device Information**: View panel details and connection status
- **Session Management**: Proper authentication, logout, and connection handling

## 🚀 Installation

### Prerequisites

- **Supported Models**: AMT 1016 NET, AMT 2018 NET, and other AMT series panels
- **Network Access**: Your alarm panel must be connected to your local network
- **Hex Password**: You'll need your panel's password (4-6 digits, e.g., "1234", "878787")

### HACS Installation (Recommended)

This integration can be installed through HACS as a custom repository:

1. **Add Custom Repository:**

   - Open HACS → Integrations
   - Click ⋮ menu → Custom repositories
   - Add: `https://github.com/intelbras-community/ha-intelbras-alarm`
   - Category: Integration

2. **Install Integration:**

   - Search for "Intelbras Alarm"
   - Click "Download" and restart Home Assistant

3. **Configure Integration:**
   - Go to **Settings** → **Devices & Services** → **Add Integration**
   - Search for "Intelbras Alarm" and select it
   - Enter your panel's IP address and hex password

### Manual Installation (Alternative)

If you prefer to install manually:

1. Download the latest release from [GitHub Releases](https://github.com/intelbras-community/ha-intelbras-alarm/releases)
2. Extract the `custom_components/intelbras_alarm` folder to your Home Assistant `custom_components` directory
   - Your path should look like: `config/custom_components/intelbras_alarm/`
3. Restart Home Assistant
4. Go to **Settings** → **Devices & Services** → **Add Integration**
5. Search for "Intelbras Alarm" and select it
6. Enter your panel's IP address and hex password

## Configuration

### Through the UI

1. Navigate to **Settings** → **Devices & Services**
2. Click the **+** button to add a new integration
3. Search for "Intelbras Alarm"
4. Enter your connection details:
   - **Panel IP Address**: Your alarm panel's local network IP (e.g., 192.168.0.100)
   - **Password**: Your panel's hex password (4-6 digits, same as used in Android app)
   - **Port**: TCP port (default: 9009)

### Manual Configuration (Not Recommended)

This integration supports configuration through the UI only. Manual YAML configuration is not supported.

## Usage

### Alarm Control Panel

The integration creates an alarm control panel entity that provides:

- **Arm/Disarm Control**: Toggle your alarm system's armed state
- **Status Monitoring**: Real-time display of current alarm state
- **Device Information**: Panel details including IP, MAC address, and model

### Binary Sensors

Additional binary sensors provide monitoring capabilities:

- **Connection Status**: Monitor panel connectivity (`binary_sensor.panel_connection`)
- **Alarm Status**: Current alarm state (`binary_sensor.panel_alarm`)
- **System Problems**: Alert for system issues (`binary_sensor.panel_problems`)

### Switch Entities (PGM Control)

Control programmable outputs through switch entities:

- **PGM 1-4**: Toggle programmable outputs (`switch.panel_pgm_1`, etc.)
- **Real-time Status**: Shows current state of each PGM output
- **Device Control**: Same functionality as the Android app's PGM controls

### Sensors

Additional sensors provide detailed monitoring information:

- **System Status**: Overall alarm system state (`sensor.panel_system_status`)
- **Active Zones**: Count of active zones (`sensor.panel_active_zones`)
- **Last Update**: Timestamp of most recent status update (`sensor.panel_last_update`)


[commits-shield]: https://img.shields.io/github/commit-activity/y/tarikbc/ha-ppa-contatto.svg?style=for-the-badge
[commits]: https://github.com/tarikbc/ha-ppa-contatto/commits/main
[maintenance-shield]: https://img.shields.io/badge/maintainer-Tarik%20Caramanico%20%40tarikbc-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/tarikbc/ha-ppa-contatto.svg?style=for-the-badge
[releases]: https://github.com/tarikbc/ha-ppa-contatto/releases
[user_profile]: https://github.com/tarikbc
