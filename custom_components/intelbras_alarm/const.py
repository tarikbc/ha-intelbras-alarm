"""Constants for the Intelbras Alarm integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "intelbras_alarm"
DEFAULT_NAME: Final = "Intelbras Alarm"

# Configuration flow constants
CONF_PANEL_IP: Final = "panel_ip"
CONF_PASSWORD: Final = "password"
CONF_PORT: Final = "port"

# Default values
DEFAULT_PORT: Final = 9009
DEFAULT_TIMEOUT: Final = 15
DEFAULT_RETRIES: Final = 3
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds

# Connection types
CONNECTION_TYPE_LOCAL: Final = "local"

# Discovery
DISCOVERY_PORT: Final = 9009
DISCOVERY_TIMEOUT: Final = 3

# Device info
MANUFACTURER: Final = "Intelbras"
MODEL_PREFIX: Final = "AMT"

# === NATIVE INTELBRAS PROTOCOL (0xe7) ===
NATIVE_PROTOCOL_ID: Final = 0xE7  # Protocol identifier (231 decimal)

# === AUTHENTICATION PROTOCOL ===
NATIVE_AUTH_REQUEST: Final = 0x09  # Authentication request prefix (09e7051182745a34edef9f)
NATIVE_AUTH_SUBTYPE: Final = 0x05  # Authentication subtype
NATIVE_AUTH_CMD: Final = 0x11  # Authentication command
NATIVE_AUTH_CONSTANTS: Final = [0x34, 0xED, 0xEF, 0x9F]  # Constants appended to encoded password

# === STATUS COMMANDS ===
NATIVE_STATUS_REQUEST: Final = 0x05  # Status request prefix
NATIVE_SUBTYPE_STATUS: Final = 0x01  # Status subtype

# Simple status (unauthenticated) - returns 7 bytes: 05e7019085636a
NATIVE_CMD_SIMPLE_STATUS: Final = 0x10

# Authenticated status - returns 32 bytes with armed state in byte 6
NATIVE_CMD_AUTH_STATUS: Final = 0x17  # Authenticated status command (05e701178671fc)

# === CONTROL COMMANDS ===
# Arm/Disarm toggle command - works as toggle (armed->disarmed, disarmed->armed)
NATIVE_CMD_ARM_DISARM: Final = 0x06  # Command prefix for arm/disarm toggle
NATIVE_ARM_DISARM_SUBTYPE: Final = 0x02  # Subtype for arm/disarm
NATIVE_ARM_DISARM_CMD: Final = 0x16  # Command byte
NATIVE_ARM_DISARM_DATA: Final = [0x00, 0x74, 0x28, 0x56]  # Fixed data for toggle

# PGM Control Commands - toggle commands (ON->OFF, OFF->ON)
NATIVE_CMD_PGM: Final = 0x06  # Command prefix for PGM
NATIVE_PGM_SUBTYPE: Final = 0x02  # Subtype for PGM commands
NATIVE_PGM_CMD: Final = 0x19  # Command byte for PGM

# PGM command data - byte 4 determines PGM number, increments by 0x20
# From confirmed packet captures - PGM 1 and 2 tested, 3 and 4 predicted
NATIVE_PGM1_DATA: Final = [0x60, 0x57, 0x68, 0x5A]  # PGM 1 toggle (confirmed working)
NATIVE_PGM2_DATA: Final = [0x80, 0xD5, 0x2B, 0x7B]  # PGM 2 toggle (confirmed working)
NATIVE_PGM3_DATA: Final = [0xA0, 0x53, 0x0B, 0x38]  # PGM 3 toggle (predicted pattern)
NATIVE_PGM4_DATA: Final = [0xC0, 0xD1, 0x6B, 0x19]  # PGM 4 toggle (predicted pattern)

# === SESSION MANAGEMENT ===
NATIVE_LOGOUT_REQUEST: Final = 0x05  # Logout request prefix
NATIVE_LOGOUT_SUBTYPE: Final = 0x01  # Logout subtype
NATIVE_LOGOUT_CMD: Final = 0x15  # Logout command (05e70115067e71)
NATIVE_LOGOUT_DATA: Final = [0x06, 0x7E, 0x71]  # Logout data

# === RESPONSE ANALYSIS ===
# Armed state detection in authenticated status response (32 bytes)
NATIVE_STATUS_ARMED_BYTE: Final = 6  # Byte index for armed state (0-based)
NATIVE_STATUS_DISARMED: Final = 0x00  # Value when disarmed
NATIVE_STATUS_ARMED: Final = 0x03  # Value when armed

# PGM state detection in toggle response
NATIVE_PGM_STATE_BYTE: Final = 5  # Byte index for PGM state in response
NATIVE_PGM_ON_VALUES: Final = [0x40, 0x57, 0x60, 0xD6]  # Added 0xd6 based on actual panel response
NATIVE_PGM_OFF_VALUES: Final = [0x20, 0x00]  # Values indicating PGM is OFF

# === PACKET STRUCTURE REFERENCE ===
# Format: [PREFIX][0xe7][SUBTYPE][CMD][DATA...][CHECKSUM]
#
# Examples from packet capture:
# Initial status:     05e7011006606a
# Authentication:     09e705111234603454edef9f (password 123456 -> 1234603454edef9f)
# Auth status:        05e701178671fc
# Arm/disarm toggle:  06e7021600742856
# PGM 1 toggle:       06e702196057685a
# PGM 2 toggle:       06e7021980d52b7b
# Logout:             05e70115067e71
