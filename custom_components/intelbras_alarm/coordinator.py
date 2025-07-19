"""Data update coordinator for Intelbras alarm."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
import binascii
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PANEL_IP,
    CONF_PASSWORD,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


class IntelbrasAlarmCoordinator(DataUpdateCoordinator):
    """Coordinator for Intelbras Alarm."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.connector = None  # This will be initialized in the future

        # Extract connection info for device registry
        self.panel_ip = entry.data.get(CONF_PANEL_IP, "Unknown")
        self.password = entry.data.get(CONF_PASSWORD, "")

        # Determine device model and identifiers
        self.device_model = self._determine_device_model()
        self.device_identifiers = self._get_device_identifiers()

        # Timestamp tracking
        self._last_successful_update: datetime | None = None

        # Connection control - enabled by default
        self._connection_enabled = True

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _determine_device_model(self) -> str:
        """Determine the device model based on available information."""
        # For now, default to AMT series since that's what we support
        return f"{MODEL_PREFIX} Panel"

    def _get_device_identifiers(self) -> set[tuple[str, str]]:
        """Get device identifiers for device registry."""
        # Use IP address as identifier for local connections
        return {(DOMAIN, self.panel_ip)}

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        # Try to get firmware version from latest status
        firmware_version = "Unknown"
        if self.data and "status" in self.data:
            status = self.data["status"]
            if status.get("firmware_version"):
                firmware_version = status["firmware_version"]

        return {
            "identifiers": self.device_identifiers,
            "name": f"Intelbras {self.device_model}",
            "manufacturer": MANUFACTURER,
            "model": self.device_model,
            "sw_version": firmware_version,
        }

    @property
    def panel_info(self) -> dict[str, Any]:
        """Return panel information."""
        return {
            "ip": self.panel_ip,
            "model": self.device_model,
            "manufacturer": MANUFACTURER,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        # Check if connection is enabled via the connection control switch
        if not self._connection_enabled:
            _LOGGER.debug("Connection disabled via switch - disconnecting and clearing data")

            # Disconnect and cleanup connector when disabled
            if self.connector:
                try:
                    await self.connector.async_disconnect()
                except Exception as ex:
                    _LOGGER.debug("Error during disconnect: %s", ex)
                finally:
                    self.connector = None

            # Clear last successful update timestamp so entities show as unavailable
            self._last_successful_update = None

            # Return disconnected status with no cached data
            return {
                "status": {
                    "connected": False,
                    "authenticated": False,
                    "armed": None,  # Unknown state
                    "partial_armed": None,  # Unknown state
                    "alarm": None,  # Unknown state
                    "pgms": [],  # No PGM data when disconnected
                    "events": [],
                    "connection_disabled": True,
                    "source_voltage": None,
                    "battery_voltage": None,
                    "siren_status": None,
                    "battery_missing": None,
                    "firmware_version": None,
                },
                "panel_info": self.panel_info,
                "last_update": time.time(),
            }

        try:
            if not self.connector:
                from .protocol import IntelbrasConnector

                self.connector = IntelbrasConnector(self.entry.data)

            # Get current status
            status = await self.connector.async_get_status()

            # Update timestamp on successful data retrieval
            self._last_successful_update = dt_util.now()

            return {
                "status": status,
                "panel_info": self.panel_info,
                "last_update": time.time(),
            }

        except Exception as err:
            _LOGGER.error("Error communicating with alarm panel: %s", err)
            raise UpdateFailed(f"Error communicating with alarm panel: {err}")

    # Control methods
    async def async_arm(self, mode: str = "away") -> bool:
        """Arm the alarm system with retry logic for connection resilience."""
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                if not self.connector:
                    from .protocol import IntelbrasConnector

                    self.connector = IntelbrasConnector(self.entry.data)

                _LOGGER.info("Sending ARM command (attempt %d/%d)", attempt + 1, max_retries + 1)
                success = await self.connector.async_arm()

                if success:
                    # Refresh data to get updated status
                    await asyncio.sleep(0.5)  # Brief delay for panel to process
                    await self.async_request_refresh()

                _LOGGER.info("ARM command result: %s", "SUCCESS" if success else "FAILED")
                return success

            except Exception as err:
                _LOGGER.warning("Error arming panel (attempt %d/%d): %s", attempt + 1, max_retries + 1, err)
                if attempt < max_retries:
                    _LOGGER.info("Retrying arm command in 1 second...")
                    await asyncio.sleep(1)
                else:
                    _LOGGER.error("All arm attempts failed")
                    return False

        return False

    async def async_disarm(self) -> bool:
        """Disarm the alarm system with retry logic for connection resilience."""
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                if not self.connector:
                    from .protocol import IntelbrasConnector

                    self.connector = IntelbrasConnector(self.entry.data)

                _LOGGER.info("Sending DISARM command (attempt %d/%d)", attempt + 1, max_retries + 1)
                success = await self.connector.async_disarm()

                if success:
                    # Refresh data to get updated status
                    await asyncio.sleep(0.5)  # Brief delay for panel to process
                    await self.async_request_refresh()

                _LOGGER.info("DISARM command result: %s", "SUCCESS" if success else "FAILED")
                return success

            except Exception as err:
                _LOGGER.warning("Error disarming panel (attempt %d/%d): %s", attempt + 1, max_retries + 1, err)
                if attempt < max_retries:
                    _LOGGER.info("Retrying disarm command in 1 second...")
                    await asyncio.sleep(1)
                else:
                    _LOGGER.error("All disarm attempts failed")
                    return False

        return False

    async def async_trigger_pgm(self, pgm_id: int) -> bool:
        """Trigger PGM output (same as set_pgm with toggle behavior)."""
        try:
            if not self.connector:
                from .protocol import IntelbrasConnector

                self.connector = IntelbrasConnector(self.entry.data)

            _LOGGER.info("Triggering PGM %s", pgm_id)
            success = await self.connector.async_set_pgm(pgm_id, True)  # State doesn't matter for toggle

            if success:
                # Refresh data to get updated status
                await asyncio.sleep(0.5)  # Brief delay for panel to process
                await self.async_request_refresh()

            _LOGGER.info("PGM %s trigger result: %s", pgm_id, "SUCCESS" if success else "FAILED")
            return success

        except Exception as ex:
            _LOGGER.error("Failed to trigger PGM %s: %s", pgm_id, ex)
            return False

    async def async_set_pgm(self, pgm_id: int, state: bool) -> bool:
        """Set PGM output with retry logic for connection resilience."""
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                if not self.connector:
                    from .protocol import IntelbrasConnector

                    self.connector = IntelbrasConnector(self.entry.data)

                action = "enable" if state else "disable"
                _LOGGER.info("Setting PGM %s to %s (attempt %d/%d)", pgm_id, action, attempt + 1, max_retries + 1)

                # Send PGM command - protocol layer handles state tracking
                success = await self.connector.async_set_pgm(pgm_id, state)

                if success:
                    # Refresh data to update UI with new state
                    await asyncio.sleep(0.3)  # Brief delay for panel to process
                    await self.async_request_refresh()

                    _LOGGER.info("PGM %s %s result: SUCCESS", pgm_id, action)
                    return True
                else:
                    _LOGGER.warning("PGM %s %s result: FAILED", pgm_id, action)

            except Exception as ex:
                action = "enable" if state else "disable"
                _LOGGER.warning(
                    "Failed to %s PGM %s (attempt %d/%d): %s", action, pgm_id, attempt + 1, max_retries + 1, ex
                )
                if attempt < max_retries:
                    _LOGGER.info("Retrying PGM %s command in 1 second...", pgm_id)
                    await asyncio.sleep(1)
                else:
                    _LOGGER.error("All PGM %s attempts failed", pgm_id)
                    return False

        return False

    def get_pgm_status(self, pgm_id: int) -> dict[str, Any] | None:
        """Get status of a specific PGM."""
        if not self.connector:
            return None

        return self.connector.get_pgm_status(pgm_id)

    def get_alarm_status(self) -> dict[str, Any]:
        """Get alarm status in format expected by alarm_control_panel."""
        if not self.connector:
            return {"armed": False, "partial_armed": False, "alarm": False}

        return self.connector.get_alarm_status()

    def get_connection_info(self) -> dict[str, Any]:
        """Get connection information for debugging."""
        if not self.connector:
            return {
                "connector_initialized": False,
                "panel_ip": self.panel_ip,
                "last_update_success": self.last_update_success,
                "data_available": self.data is not None,
            }

        info = self.connector.get_connection_info()
        info.update(
            {
                "coordinator_initialized": True,
                "last_update_success": self.last_update_success,
                "data_available": self.data is not None,
            }
        )

        return info

    @property
    def last_successful_update_time(self) -> datetime | None:
        """Get the timestamp of the last successful update."""
        return self._last_successful_update

    # Legacy methods for backwards compatibility
    async def async_arm_away(self) -> bool:
        """Legacy method - arm in away mode."""
        return await self.async_arm("away")

    async def async_arm_home(self) -> bool:
        """Legacy method - arm in home mode."""
        return await self.async_arm("home")  # For now, same as away

    async def async_arm_night(self) -> bool:
        """Legacy method - arm in night mode."""
        return await self.async_arm("night")  # For now, same as away

    async def async_arm_vacation(self) -> bool:
        """Legacy method - arm in vacation mode."""
        return await self.async_arm("vacation")  # For now, same as away

    async def async_arm_custom_bypass(self) -> bool:
        """Legacy method - arm with custom bypass."""
        return await self.async_arm("custom")  # For now, same as away

    async def async_disconnect(self) -> None:
        """Disconnect from the panel."""
        if self.connector:
            await self.connector.async_disconnect()
            self.connector = None

    def get_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent events."""
        if not self.data or "status" not in self.data:
            return []

        events = self.data["status"].get("events", [])
        return events[:limit]
