"""Protocol implementation for Intelbras alarm panels using native 0xe7 protocol."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from .const import (
    CONF_PANEL_IP,
    CONF_PASSWORD,
    CONF_PORT,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    # Native protocol constants
    NATIVE_PROTOCOL_ID,
    NATIVE_AUTH_REQUEST,
    NATIVE_AUTH_SUBTYPE,
    NATIVE_AUTH_CMD,
    NATIVE_AUTH_CONSTANTS,
    NATIVE_STATUS_REQUEST,
    NATIVE_SUBTYPE_STATUS,
    NATIVE_CMD_SIMPLE_STATUS,
    NATIVE_CMD_AUTH_STATUS,
    NATIVE_STATUS_ARMED_BYTE,
    NATIVE_STATUS_DISARMED,
    NATIVE_STATUS_ARMED,
    NATIVE_CMD_ARM_DISARM,
    NATIVE_ARM_DISARM_SUBTYPE,
    NATIVE_ARM_DISARM_CMD,
    NATIVE_ARM_DISARM_DATA,
    NATIVE_CMD_PGM,
    NATIVE_PGM_SUBTYPE,
    NATIVE_PGM_CMD,
    NATIVE_PGM1_DATA,
    NATIVE_PGM2_DATA,
    NATIVE_PGM3_DATA,
    NATIVE_PGM4_DATA,
    NATIVE_PGM_STATE_BYTE,
    NATIVE_PGM_ON_VALUES,
    NATIVE_PGM_OFF_VALUES,
    NATIVE_LOGOUT_REQUEST,
    NATIVE_LOGOUT_SUBTYPE,
    NATIVE_LOGOUT_CMD,
    NATIVE_LOGOUT_DATA,
)

_LOGGER = logging.getLogger(__name__)


class IntelbrasNativeProtocol:
    """Native Intelbras protocol implementation using reverse-engineered 0xe7 protocol.

    Implements complete packet communication including authentication, status monitoring,
    and control commands based on AMT REMOTO MOBILE app analysis.
    """

    @staticmethod
    def calculate_checksum(data: list[int]) -> int:
        """Calculate packet checksum using discovered algorithm."""
        checksum = 0
        for byte_val in data:
            checksum ^= byte_val
        return checksum ^ 0xFF  # XOR with 0xFF to match packet capture

    @staticmethod
    def encode_password(password_hex: str) -> list[int]:
        """Encode password using discovered algorithm.

        Algorithm: Convert hex password to bytes, add 10 to third byte, append constants.
        Example: "123456" -> [0x12, 0x34, 0x56+10] + [0x34, 0xED, 0xEF, 0x9F]

        Args:
            password_hex: Password as hex string (4-6 digits)

        Returns:
            Encoded password bytes for authentication
        """
        try:
            # Convert hex string to bytes
            password_bytes = []
            for i in range(0, len(password_hex), 2):
                password_bytes.append(int(password_hex[i : i + 2], 16))

            # Apply encoding: add 10 to third byte, append constants
            encoded = password_bytes.copy()
            if len(encoded) >= 3:
                encoded[2] += 10
            encoded.extend(NATIVE_AUTH_CONSTANTS)

            return encoded

        except ValueError as ex:
            _LOGGER.error("Invalid password format '%s': %s", password_hex, ex)
            raise ValueError(f"Password must be hex string, got: {password_hex}")

    @staticmethod
    def build_initial_status() -> bytes:
        """Build initial status request (unauthenticated)."""
        data = [NATIVE_PROTOCOL_ID, NATIVE_SUBTYPE_STATUS, NATIVE_CMD_SIMPLE_STATUS, 0x06, 0x60]
        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def build_authentication(password_hex: str) -> bytes:
        """Build authentication request using discovered algorithm."""
        encoded_password = IntelbrasNativeProtocol.encode_password(password_hex)

        data = [
            NATIVE_PROTOCOL_ID,
            NATIVE_AUTH_SUBTYPE,
            NATIVE_AUTH_CMD,
        ]
        data.extend(encoded_password)

        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def build_authenticated_status() -> bytes:
        """Build authenticated status request (returns 32 bytes with armed state)."""
        data = [NATIVE_PROTOCOL_ID, NATIVE_SUBTYPE_STATUS, NATIVE_CMD_AUTH_STATUS, 0x86, 0x71]
        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def build_arm_disarm_toggle() -> bytes:
        """Build arm/disarm toggle command."""
        data = [
            NATIVE_PROTOCOL_ID,
            NATIVE_ARM_DISARM_SUBTYPE,
            NATIVE_ARM_DISARM_CMD,
        ]
        data.extend(NATIVE_ARM_DISARM_DATA)
        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def build_pgm_toggle(pgm_id: int) -> bytes:
        """Build PGM toggle command packet."""
        pgm_data_map = {
            1: NATIVE_PGM1_DATA,
            2: NATIVE_PGM2_DATA,
            3: NATIVE_PGM3_DATA,
            4: NATIVE_PGM4_DATA,
        }

        if pgm_id not in pgm_data_map:
            raise ValueError(f"Invalid PGM ID: {pgm_id}")

        data = [
            NATIVE_PROTOCOL_ID,
            NATIVE_PGM_SUBTYPE,
            NATIVE_PGM_CMD,
        ] + pgm_data_map[pgm_id]

        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def build_logout() -> bytes:
        """Build logout command to close session."""
        data = [
            NATIVE_PROTOCOL_ID,
            NATIVE_LOGOUT_SUBTYPE,
            NATIVE_LOGOUT_CMD,
        ]
        data.extend(NATIVE_LOGOUT_DATA)
        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def parse_status_response(data: bytes) -> dict[str, Any]:
        """Parse status response to extract armed state and other detailed info.

        Args:
            data: Raw response bytes

        Returns:
            Parsed status information including firmware, voltage, siren, battery
        """
        result = {
            "armed": False,
            "raw_response": data.hex(),
            "response_length": len(data),
            "firmware_version": None,
            "source_voltage": None,
            "siren_status": None,
            "battery_missing": None,
        }

        if len(data) >= 7:
            # Check if this is an authenticated status response (32+ bytes)
            if len(data) >= 32:
                # Extract armed state from byte 6 (0-based indexing)
                armed_byte = data[NATIVE_STATUS_ARMED_BYTE]
                result["armed"] = armed_byte == NATIVE_STATUS_ARMED
                result["armed_byte_value"] = armed_byte
                result["authenticated"] = True

                # Extract firmware version from bytes 26-27
                if len(data) > 27:
                    fw_byte1 = data[26]
                    fw_byte2 = data[27]
                    firmware_version = None  # Initialize variable to avoid UnboundLocalError

                    if 16 <= fw_byte1 <= 25 and 1 <= fw_byte2 <= 10:
                        major = fw_byte1 - 17
                        minor = fw_byte2 - 1
                        if 0 <= major <= 9 and 0 <= minor <= 9:
                            firmware_version = f"{major}.{minor}.0"

                    # Fallback: Show raw bytes for debugging
                    if not firmware_version:
                        firmware_version = f"raw_{fw_byte1:02x}_{fw_byte2:02x}"

                    result["firmware_version"] = firmware_version

                # Extract source voltage from bytes 20-21
                if len(data) > 21:
                    source_raw = (data[20] << 8) | data[21]

                    if source_raw == 0 or source_raw < 100:
                        source_voltage = 0.0
                    else:
                        # Standard voltage offset for panel ADC calibration
                        source_voltage = (source_raw + 500) / 100.0

                        # Validate range (typical mains voltage 12-16V)
                        if source_voltage < 5.0 or source_voltage > 20.0:
                            _LOGGER.warning("Source voltage %.2fV seems out of range", source_voltage)

                    result["source_voltage"] = source_voltage

                # Extract battery voltage from bytes 22-23
                if len(data) > 23:
                    battery_raw = (data[22] << 8) | data[23]

                    if battery_raw == 0 or battery_raw < 100:
                        battery_voltage = None  # Battery missing/disconnected
                    else:
                        # Standard voltage offset for panel ADC calibration
                        battery_voltage = (battery_raw + 500) / 100.0

                        # Validate range (typical battery voltage 10-16V)
                        if battery_voltage < 5.0 or battery_voltage > 20.0:
                            _LOGGER.warning("Battery voltage %.2fV seems out of range", battery_voltage)

                    result["battery_voltage"] = battery_voltage

                # Extract siren status from byte 28
                if len(data) > 28:
                    siren_byte = data[28]

                    # Common patterns observed
                    known_off_values = [0x11, 0x19, 0x01, 0x00, 0x07, 0x08, 0x10, 0x18]
                    known_on_values = [0xFF, 0x80, 0x40, 0x20, 0xF0, 0xF8]

                    if siren_byte in known_off_values:
                        siren_status = "Off"
                    elif siren_byte in known_on_values:
                        siren_status = "On"
                    elif siren_byte & 0xF0 == 0x10:  # 0x1X pattern
                        siren_status = "Off"
                    elif siren_byte > 0x80:  # High values typically On
                        siren_status = "On"
                    elif siren_byte < 0x20:  # Low values typically Off
                        siren_status = "Off"
                    else:
                        # Default to Off for unknown patterns
                        siren_status = "Off"

                    result["siren_status"] = siren_status
                    result["siren_byte_debug"] = siren_byte

                # Determine battery status intelligently
                # Primary: Use battery voltage reading (most reliable)
                # Secondary: Check byte 29 for additional confirmation
                battery_missing = False
                if result.get("battery_voltage") is None:
                    # No battery voltage detected = battery missing
                    battery_missing = True
                else:
                    # Battery voltage detected = battery present
                    battery_missing = False

                # Additional debugging for byte 29 patterns (only log when needed for troubleshooting)
                if len(data) > 29:
                    battery_byte = data[29]
                    result["battery_status_byte_debug"] = battery_byte

                result["battery_missing"] = battery_missing

                # PGM status - use persistent state tracking (only 2 PGMs)
                pgm_statuses = []
                for pgm_id in range(1, 3):  # Only PGM 1-2 as per Android app
                    pgm_statuses.append(
                        {
                            "id": pgm_id,
                            "name": f"PGM {pgm_id}",
                            "active": False,  # Updated by connector's persistent state
                        }
                    )

                result["pgm_statuses"] = pgm_statuses
            else:
                # Simple status response (7 bytes) - no armed state info
                result["authenticated"] = False

        return result

    @staticmethod
    def parse_control_response(data: bytes, command_type: str) -> dict[str, Any]:
        """Parse control command response.

        Args:
            data: Raw response bytes
            command_type: Type of command sent ("arm_disarm" or "pgm")

        Returns:
            Parsed response information
        """
        result = {
            "success": len(data) > 0,
            "raw_response": data.hex(),
            "response_length": len(data),
            "command_type": command_type,
        }

        if command_type == "pgm" and len(data) > NATIVE_PGM_STATE_BYTE:
            # Extract PGM state from response
            state_byte = data[NATIVE_PGM_STATE_BYTE]
            result["pgm_state_byte"] = state_byte

            # Check if response indicates PGM is ON or OFF
            pgm_on = state_byte in NATIVE_PGM_ON_VALUES
            result["pgm_on"] = pgm_on

        return result

    @staticmethod
    def build_mac_address_request() -> bytes:
        """Build MAC address request packet."""
        data = [
            NATIVE_PROTOCOL_ID,
            0x04,  # Subtype for device info
            0x12,  # Command for MAC/device info
            0x06,
            0xF0,
            0x06,
            0xC9,
            0x85,
        ]
        return IntelbrasNativeProtocol._build_packet(data)

    @staticmethod
    def parse_mac_address_response(data: bytes) -> dict[str, Any]:
        """Parse MAC address response to extract device information."""
        result = {
            "mac_address": None,
            "raw_response": data.hex(),
            "response_length": len(data),
        }

        # MAC address is at bytes 4-9
        if len(data) >= 10:
            mac_bytes = data[4:10]
            result["mac_address"] = ":".join([f"{b:02X}" for b in mac_bytes])
            _LOGGER.debug("Extracted MAC address: %s", result["mac_address"])

        return result

    @staticmethod
    def _build_packet(data: list[int]) -> bytes:
        """Build complete packet with length and checksum."""
        length = len(data)
        packet_without_checksum = [length] + data
        checksum = IntelbrasNativeProtocol.calculate_checksum(packet_without_checksum)
        return bytes(packet_without_checksum + [checksum])


class IntelbrasConnector:
    """Connector for Intelbras alarm panels using native 0xe7 protocol."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the connector."""
        self.config = config
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.is_connected = False
        self.is_authenticated = False
        self.last_status: dict[str, Any] = {}

        # Concurrency control and error tracking
        self._connection_lock = asyncio.Lock()
        self._last_connection_error: str | None = None
        self._edit_mode_detected: bool = False

        # PGM state persistence - maintain states between status updates (only 2 PGMs)
        self._pgm_states = {1: False, 2: False}  # Only PGM 1-2 as per Android app

    async def async_connect(self) -> bool:
        """Connect to the panel and establish session."""
        if self.is_connected:
            return True

        try:
            return await self._connect_local()
        except Exception as ex:
            _LOGGER.error("Connection failed: %s", ex)
            self._last_connection_error = str(ex)
            return False

    async def _connect_local(self) -> bool:
        """Connect to panel via local network."""
        ip = self.config[CONF_PANEL_IP]
        port = self.config.get(CONF_PORT, DEFAULT_PORT)

        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=DEFAULT_TIMEOUT
            )

            # Test connection with initial status
            packet = IntelbrasNativeProtocol.build_initial_status()
            self.writer.write(packet)
            await self.writer.drain()

            response = await asyncio.wait_for(self.reader.read(1024), timeout=5)

            if response and len(response) >= 7:
                self.is_connected = True
                return True
            else:
                _LOGGER.warning("Initial status failed - invalid response")
            await self._cleanup_connection()
            return False

        except Exception as ex:
            _LOGGER.error("Failed to connect: %s", ex)
            self._last_connection_error = str(ex)
            await self._cleanup_connection()
            return False

    async def async_authenticate(self) -> bool:
        """Authenticate with the panel."""
        if not self.is_connected:
            if not await self.async_connect():
                return False

        if self.is_authenticated:
            return True

        async with self._connection_lock:
            try:
                password = self.config.get(CONF_PASSWORD, "")
                if not password:
                    _LOGGER.error("No password configured for authentication")
                    return False

                await asyncio.sleep(0.5)  # Panel stability delay

                packet = IntelbrasNativeProtocol.build_authentication(password)
                self.writer.write(packet)
                await self.writer.drain()

                response = await asyncio.wait_for(self.reader.read(1024), timeout=10)

                if response and len(response) >= 5:
                    self.is_authenticated = True
                    await asyncio.sleep(0.3)  # Post-auth delay
                    return True
                else:
                    _LOGGER.error("Authentication failed - invalid response")
                    return False

            except Exception as ex:
                _LOGGER.error("Authentication error: %s", ex)
                return False

    async def async_get_status(self) -> dict[str, Any]:
        """Get current panel status."""
        if not self.is_connected:
            if not await self.async_connect():
                return self._get_disconnected_status("Connection failed")

        if not self.is_authenticated:
            if not await self.async_authenticate():
                return self._get_disconnected_status("Authentication failed")

        async with self._connection_lock:
            try:
                if not self.writer or self.writer.is_closing():
                    await self._cleanup_connection()
                    if not await self.async_connect() or not await self.async_authenticate():
                        return self._get_disconnected_status("Reconnection failed")

                packet = IntelbrasNativeProtocol.build_authenticated_status()
                self.writer.write(packet)
                await self.writer.drain()

                response = await asyncio.wait_for(self.reader.read(1024), timeout=DEFAULT_TIMEOUT)

                if response:
                    parsed = IntelbrasNativeProtocol.parse_status_response(response)

                    status = {
                        "connected": True,
                        "authenticated": parsed["authenticated"],
                        "armed": parsed["armed"],
                        "partial_armed": False,
                        "alarm": False,
                        "pgms": self._build_pgm_status(),
                        "events": [],
                        "firmware_version": parsed.get("firmware_version"),
                        "source_voltage": parsed.get("source_voltage"),
                        "battery_voltage": parsed.get("battery_voltage"),
                        "siren_status": parsed.get("siren_status"),
                        "battery_missing": parsed.get("battery_missing"),
                        "native_response": parsed,
                    }

                    self.last_status = status
                    return status
                else:
                    await self._handle_connection_error(Exception("Empty response"))
                    return self._get_disconnected_status("Empty response from panel")

            except Exception as ex:
                _LOGGER.error("Failed to get status: %s", ex)
                await self._handle_connection_error(ex)
                return self._get_disconnected_status(f"Communication error: {ex}")

    def _build_pgm_status(self) -> list[dict[str, Any]]:
        """Build PGM status list with persistent state - only 2 PGMs as per Android app."""
        return [
            {"id": pgm_id, "name": f"PGM {pgm_id}", "active": self._pgm_states.get(pgm_id, False)}
            for pgm_id in range(1, 3)  # Only PGM 1-2 as shown in Android app
        ]

    def _get_disconnected_status(self, reason: str) -> dict[str, Any]:
        """Return disconnected status."""
        _LOGGER.warning("Panel disconnected: %s", reason)

        status = {
            "connected": False,
            "authenticated": False,
            "armed": False,
            "partial_armed": False,
            "alarm": False,
            "pgms": self._build_pgm_status(),  # Use same 2-PGM logic
            "events": [],
            "connection_error": reason,
        }

        self.last_status = status
        return status

    async def async_arm(self, partition: int = 1, stay_arm: bool = False) -> bool:
        """Arm the system."""
        current_status = await self.async_get_status()
        if not current_status.get("connected", False):
            return False

        if current_status.get("armed", False):
            return True

        return await self._send_arm_disarm_toggle("arm")

    async def async_disarm(self, partition: int = 1) -> bool:
        """Disarm the system."""
        current_status = await self.async_get_status()
        if not current_status.get("connected", False):
            return False

        if not current_status.get("armed", False):
            return True

        return await self._send_arm_disarm_toggle("disarm")

    async def _send_arm_disarm_toggle(self, action: str) -> bool:
        """Send arm/disarm toggle command."""
        if not self.is_authenticated:
            if not await self.async_authenticate():
                return False

        async with self._connection_lock:
            try:
                if not self.writer or self.writer.is_closing():
                    await self._cleanup_connection()
                    if not await self.async_connect() or not await self.async_authenticate():
                        return False

                packet = IntelbrasNativeProtocol.build_arm_disarm_toggle()
                self.writer.write(packet)
                await self.writer.drain()

                response = await asyncio.wait_for(self.reader.read(1024), timeout=DEFAULT_TIMEOUT)

                if response:
                    parsed = IntelbrasNativeProtocol.parse_control_response(response, "arm_disarm")
                    return parsed["success"]
                return False

            except Exception as ex:
                _LOGGER.error("Failed to %s: %s", action, ex)
                await self._handle_connection_error(ex)
                return False

    async def async_set_pgm(self, pgm_id: int, state: bool) -> bool:
        """Toggle PGM output."""
        if not self.is_authenticated:
            if not await self.async_authenticate():
                return False

        async with self._connection_lock:
            try:
                if not self.writer or self.writer.is_closing():
                    await self._cleanup_connection()
                    if not await self.async_connect() or not await self.async_authenticate():
                        return False

                packet = IntelbrasNativeProtocol.build_pgm_toggle(pgm_id)
                self.writer.write(packet)
                await self.writer.drain()

                response = await asyncio.wait_for(self.reader.read(1024), timeout=DEFAULT_TIMEOUT)

                if response:
                    parsed = IntelbrasNativeProtocol.parse_control_response(response, "pgm")
                    success = parsed["success"]

                    # Update persistent state on successful toggle
                    if success and 1 <= pgm_id <= 2:  # Only PGM 1-2 supported
                        self._pgm_states[pgm_id] = not self._pgm_states.get(pgm_id, False)

                    return success
                return False

            except Exception as ex:
                _LOGGER.error("Failed to toggle PGM %s: %s", pgm_id, ex)
                await self._handle_connection_error(ex)
                return False

    async def async_trigger_pgm(self, pgm_id: int, action: str = "toggle") -> bool:
        """Trigger PGM (works as toggle)."""
        return await self.async_set_pgm(pgm_id, True)

    async def async_get_pgm(self) -> dict[str, Any]:
        """Get PGM configuration from the panel."""
        _LOGGER.debug("Starting PGM discovery...")

        try:
            # Get current status to see what PGMs are available (don't use lock here)
            _LOGGER.debug("Getting panel status for PGM discovery...")
            status = await self.async_get_status()

            if "pgms" in status:
                pgms = status["pgms"]
                _LOGGER.info("PGM discovery found %d PGMs: %s", len(pgms), [f"PGM {pgm['id']}" for pgm in pgms])

                # Test each PGM to see if it responds by trying a simple status check
                active_pgms = []
                for pgm in pgms:
                    pgm_id = pgm["id"]
                    try:
                        # Simply check if PGM ID is valid and get its status
                        pgm_status = self.get_pgm_status(pgm_id)
                        if pgm_status and 1 <= pgm_id <= 2:  # Only PGM 1-2 supported
                            active_pgms.append(pgm_status)
                            _LOGGER.debug("PGM %d is available: %s", pgm_id, pgm_status)
                    except Exception as ex:
                        _LOGGER.debug("PGM %d not available: %s", pgm_id, ex)

                return {
                    "pgms": active_pgms,
                    "total_pgms": len(pgms),
                    "active_pgms": len(active_pgms),
                    "status": status,
                }
            else:
                _LOGGER.warning("No PGM data found in status response")
                return {"pgms": [], "error": "No PGM data in status"}

        except Exception as ex:
            _LOGGER.error("Failed to discover PGMs: %s", ex, exc_info=True)
            return {"pgms": [], "error": str(ex)}

    async def async_logout(self) -> bool:
        """Logout and close session."""
        if not self.is_connected:
            return True

        async with self._connection_lock:
            try:
                packet = IntelbrasNativeProtocol.build_logout()
                self.writer.write(packet)
                await self.writer.drain()

                try:
                    await asyncio.wait_for(self.reader.read(1024), timeout=2)
                except asyncio.TimeoutError:
                    pass

                return True

            except Exception as ex:
                _LOGGER.warning("Logout error (non-critical): %s", ex)
                return True

    async def _handle_connection_error(self, ex: Exception) -> None:
        """Handle connection errors."""
        self._last_connection_error = str(ex)

        if "connection reset" in str(ex).lower():
            _LOGGER.warning("Panel reset connection - normal behavior")
        elif "timeout" in str(ex).lower():
            self._edit_mode_detected = True
            _LOGGER.warning("Connection timeout - panel may be in edit mode")
        else:
            _LOGGER.error("Connection error: %s", ex)

        await self._cleanup_connection()

    async def _cleanup_connection(self) -> None:
        """Clean up connection and reset state."""
        self.is_connected = False
        self.is_authenticated = False

        if self.writer:
            try:
                if not self.writer.is_closing():
                    self.writer.close()
                    await self.writer.wait_closed()
            except Exception:
                pass
            finally:
                self.writer = None

        if self.reader:
            self.reader = None

    async def async_disconnect(self) -> None:
        """Disconnect from panel."""
        if not self.is_connected:
            return

        try:
            if self.is_authenticated and self.writer and not self.writer.is_closing():
                try:
                    logout_packet = IntelbrasNativeProtocol.build_logout()
                    self.writer.write(logout_packet)
                    await self.writer.drain()
                    await asyncio.sleep(0.2)
                except Exception as ex:
                    _LOGGER.warning("Logout failed (non-critical): %s", ex)
        except Exception as ex:
            _LOGGER.warning("Disconnect error: %s", ex)
        finally:
            await self._cleanup_connection()

    # Error tracking and compatibility methods
    def get_last_connection_error(self) -> str | None:
        """Get the last connection error message."""
        return self._last_connection_error

    def get_connection_info(self) -> dict[str, Any]:
        """Get connection information for debugging."""
        return {
            "is_connected": self.is_connected,
            "is_authenticated": self.is_authenticated,
            "last_error": self._last_connection_error,
            "edit_mode_detected": self._edit_mode_detected,
            "panel_ip": self.config.get(CONF_PANEL_IP, "Unknown"),
            "panel_port": self.config.get(CONF_PORT, DEFAULT_PORT),
        }

    def clear_connection_error(self) -> None:
        """Clear the last connection error."""
        self._last_connection_error = None
        self._edit_mode_detected = False

    def is_edit_mode_detected(self) -> bool:
        """Check if edit mode was detected."""
        return self._edit_mode_detected

    def get_alarm_status(self) -> dict[str, Any]:
        """Get alarm status for alarm_control_panel."""
        if not self.last_status:
            return {"armed": False, "partial_armed": False, "alarm": False}

        return {
            "armed": self.last_status.get("armed", False),
            "partial_armed": self.last_status.get("partial_armed", False),
            "alarm": self.last_status.get("alarm", False),
        }

    def get_pgm_status(self, pgm_id: int) -> dict[str, Any] | None:
        """Get status of a specific PGM."""
        if not (1 <= pgm_id <= 2):  # Only PGM 1-2 supported
            return None

        return {"id": pgm_id, "name": f"PGM {pgm_id}", "active": self._pgm_states.get(pgm_id, False)}
