"""Switch platform for Intelbras Alarm integration."""
from __future__ import annotations

import logging
from typing import Any
import asyncio

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelbrasAlarmCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelbras switches from a config entry."""
    coordinator: IntelbrasAlarmCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SwitchEntity] = []

    entities.append(IntelbrasConnectionSwitch(coordinator))

    available_pgms = []
    if coordinator.data and "status" in coordinator.data:
        pgms = coordinator.data["status"].get("pgms", [])
        available_pgms = [pgm["id"] for pgm in pgms if pgm.get("id") and 1 <= pgm["id"] <= 4]
        _LOGGER.info("Discovered %d PGMs from panel: %s", len(available_pgms), available_pgms)

    for pgm_id in available_pgms:
        entities.append(IntelbrasPGMSwitch(coordinator, pgm_id))
        _LOGGER.debug("Added PGM %d switch", pgm_id)

    async_add_entities(entities)


class IntelbrasPGMSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an Intelbras PGM switch."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IntelbrasAlarmCoordinator, pgm_id: int) -> None:
        """Initialize the PGM switch."""
        super().__init__(coordinator)
        self.coordinator: IntelbrasAlarmCoordinator = coordinator
        self.pgm_id = pgm_id

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_pgm_{pgm_id}"

        # Get PGM name from data
        pgm_name = self._get_pgm_name()
        self._attr_name = pgm_name

        # Set device info
        self._attr_device_info = coordinator.device_info

    def _get_pgm_name(self) -> str:
        """Get the PGM name from coordinator data."""
        pgm_status = self.coordinator.get_pgm_status(self.pgm_id)
        if pgm_status:
            return pgm_status.get("name", f"PGM {self.pgm_id}")
        return f"PGM {self.pgm_id}"

    @property
    def is_on(self) -> bool:
        """Return True if PGM is active."""
        # Return False when connection is disabled (can't know real state)
        if self.coordinator.data and self.coordinator.data.get("status", {}).get("connection_disabled", False):
            return False

        pgm_status = self.coordinator.get_pgm_status(self.pgm_id)
        if not pgm_status:
            return False
        return pgm_status.get("active", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        pgm_status = self.coordinator.get_pgm_status(self.pgm_id)
        if not pgm_status:
            return {}

        return {
            "pgm_id": self.pgm_id,
            "pgm_name": pgm_status.get("name", f"PGM {self.pgm_id}"),
            "note": "PGM outputs are typically pulse/momentary - they may auto-turn off after 3-5 seconds. This is normal alarm panel behavior.",
            "output_type": "pulse/momentary",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the PGM on with retry logic."""
        _LOGGER.debug("Turning on PGM %s", self.pgm_id)

        # Retry logic for more reliable PGM control
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                success = await self.coordinator.async_set_pgm(self.pgm_id, True)
                if success:
                    _LOGGER.debug("PGM %s turned on successfully", self.pgm_id)
                    return

                _LOGGER.warning("PGM %s turn on failed (attempt %d/%d)", self.pgm_id, attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(1)  # Wait before retry

            except Exception as ex:
                _LOGGER.warning(
                    "PGM %s turn on error (attempt %d/%d): %s", self.pgm_id, attempt + 1, max_retries + 1, ex
                )
                if attempt < max_retries:
                    await asyncio.sleep(1)

        _LOGGER.error("Failed to turn on PGM %s after %d attempts", self.pgm_id, max_retries + 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the PGM off with retry logic."""
        _LOGGER.debug("Turning off PGM %s", self.pgm_id)

        # Retry logic for more reliable PGM control
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                success = await self.coordinator.async_set_pgm(self.pgm_id, False)
                if success:
                    _LOGGER.debug("PGM %s turned off successfully", self.pgm_id)
                    return

                _LOGGER.warning("PGM %s turn off failed (attempt %d/%d)", self.pgm_id, attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(1)  # Wait before retry

            except Exception as ex:
                _LOGGER.warning(
                    "PGM %s turn off error (attempt %d/%d): %s", self.pgm_id, attempt + 1, max_retries + 1, ex
                )
                if attempt < max_retries:
                    await asyncio.sleep(1)

        _LOGGER.error("Failed to turn off PGM %s after %d attempts", self.pgm_id, max_retries + 1)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is unavailable when connection is disabled
        if self.coordinator.data and self.coordinator.data.get("status", {}).get("connection_disabled", False):
            return False

        return self.coordinator.last_update_success and self.coordinator.data is not None


class IntelbrasConnectionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to control the entire alarm panel connection."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:connection"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the connection control switch."""
        super().__init__(coordinator)
        self.coordinator: IntelbrasAlarmCoordinator = coordinator

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_connection_control"
        self._attr_name = "Connection Control"

    @property
    def is_on(self) -> bool:
        """Return True if connection is enabled."""
        return getattr(self.coordinator, "_connection_enabled", True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "connection_status": "enabled" if self.is_on else "disabled",
            "panel_ip": self.coordinator.panel_ip,
            "current_state": "connected" if self.coordinator.last_update_success else "disconnected",
            "description": "Controls whether the integration attempts to connect to the alarm panel",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the alarm connection."""
        _LOGGER.info("Enabling alarm panel connection")
        self.coordinator._connection_enabled = True

        # Trigger immediate update when enabled
        await self.coordinator.async_request_refresh()

        # Update the switch state
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the alarm connection."""
        _LOGGER.info("Disabling alarm panel connection")
        self.coordinator._connection_enabled = False

        # Trigger immediate update to clear cached data and disconnect
        await self.coordinator.async_request_refresh()

        # Update the switch state
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Connection switch is always available
        return True
