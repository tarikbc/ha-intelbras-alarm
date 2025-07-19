"""Binary sensor platform for Intelbras Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up Intelbras binary sensors based on a config entry."""
    coordinator: IntelbrasAlarmCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = []

    # Add system status binary sensors
    entities.extend(
        [
            IntelbrasConnectionSensor(coordinator),
            IntelbrasAlarmSensor(coordinator),
        ]
    )

    async_add_entities(entities, update_before_add=True)


class IntelbrasConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an Intelbras connection sensor."""

    _attr_name = "Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the connection sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_connection"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return False
        return self.coordinator.data["status"].get("connected", False)


class IntelbrasAlarmSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an Intelbras alarm sensor."""

    _attr_name = "Alarm"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the alarm sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_alarm"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if alarm is triggered."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return False
        return self.coordinator.data["status"].get("alarm", False)
