"""Sensor platform for Intelbras Alarm integration."""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import IntelbrasAlarmCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intelbras sensors from a config entry."""
    coordinator: IntelbrasAlarmCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []

    # Add system diagnostic sensors
    entities.extend(
        [
            IntelbrasLastUpdateSensor(coordinator),
            IntelbrasSystemStatusSensor(coordinator),
            IntelbrasSourceVoltageSensor(coordinator),
            IntelbrasBatteryVoltageSensor(coordinator),
            IntelbrasSirenStatusSensor(coordinator),
            IntelbrasBatteryStatusSensor(coordinator),
        ]
    )

    async_add_entities(entities)


class IntelbrasBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Intelbras sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator: IntelbrasAlarmCoordinator = coordinator
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is unavailable when connection is disabled
        if self.coordinator.data and self.coordinator.data.get("status", {}).get("connection_disabled", False):
            return False

        return self.coordinator.last_update_success and self.coordinator.data is not None


class IntelbrasLastUpdateSensor(IntelbrasBaseSensor):
    """Sensor for last update timestamp following HA best practices."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False  # Disabled by default
    _attr_has_entity_name = True
    _attr_name = "Last Update"

    _attr_should_poll = False
    _attr_available = True

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the last update sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_last_update"

    @property
    def native_value(self) -> datetime | None:
        """Return the last successful update timestamp."""
        return self.coordinator.last_successful_update_time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "update_success": self.coordinator.last_update_success,
            "update_interval_seconds": DEFAULT_SCAN_INTERVAL,
            "panel_ip": self.coordinator.panel_ip,
            "integration_version": "native_protocol_v1.0",
        }


class IntelbrasSystemStatusSensor(IntelbrasBaseSensor):
    """Sensor for overall system status."""

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the system status sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_system_status"
        self._attr_name = "System Status"

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return "unknown"

        status = self.coordinator.data["status"]

        if status.get("alarm", False):
            return "Alarm"
        elif status.get("armed", False):
            return "Armed Away"
        elif status.get("partial_armed", False):
            return "Armed Home"
        else:
            return "Disarmed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return {}

        status = self.coordinator.data["status"]

        return {
            "armed": status.get("armed", False),
            "partial_armed": status.get("partial_armed", False),
            "alarm": status.get("alarm", False),
            "pgms_count": len(status.get("pgms", [])),
        }


class IntelbrasSourceVoltageSensor(IntelbrasBaseSensor):
    """Sensor for panel source voltage."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2  # Show 2 decimal places (14.55V)

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the source voltage sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_source_voltage"
        self._attr_name = "Source Voltage"

    @property
    def native_value(self) -> float | None:
        """Return the source voltage."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return None

        status = self.coordinator.data["status"]
        voltage = status.get("source_voltage")

        return voltage if voltage is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return {}

        return {
            "last_updated": self.coordinator.last_successful_update_time,
            "panel_info": self.coordinator.panel_info,
        }


class IntelbrasSirenStatusSensor(IntelbrasBaseSensor):
    """Sensor for siren status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the siren status sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_siren_status"
        self._attr_name = "Siren Status"

    @property
    def native_value(self) -> str | None:
        """Return the siren status."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            _LOGGER.debug("Siren status: No data available")
            return "Unknown"

        status = self.coordinator.data["status"]
        siren_status = status.get("siren_status")

        # Additional debugging info from raw parsing
        if "siren_byte_debug" in status:
            _LOGGER.debug("Siren debug byte: 0x%02x", status["siren_byte_debug"])
        if "siren_reason" in status:
            _LOGGER.debug("Siren interpretation reason: %s", status["siren_reason"])

        return siren_status if siren_status is not None else "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return {}

        return {
            "last_updated": self.coordinator.last_successful_update_time,
            "panel_info": self.coordinator.panel_info,
        }


class IntelbrasBatteryStatusSensor(IntelbrasBaseSensor):
    """Sensor for battery status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the battery status sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_battery_status"
        self._attr_name = "Battery Status"

    @property
    def native_value(self) -> str | None:
        """Return the battery status."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return "Unknown"

        status = self.coordinator.data["status"]
        battery_missing = status.get("battery_missing")

        if battery_missing is None:
            return "Unknown"
        elif battery_missing:
            return "Missing"
        else:
            return "Present"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return {}

        return {
            "last_updated": self.coordinator.last_successful_update_time,
            "panel_info": self.coordinator.panel_info,
        }


class IntelbrasBatteryVoltageSensor(IntelbrasBaseSensor):
    """Sensor for panel battery voltage."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the battery voltage sensor."""
        super().__init__(coordinator)

        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_battery_voltage"
        self._attr_name = "Battery Voltage"

    @property
    def native_value(self) -> float | None:
        """Return the battery voltage."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return None

        status = self.coordinator.data["status"]
        battery_voltage = status.get("battery_voltage")

        return battery_voltage if battery_voltage is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "status" not in self.coordinator.data:
            return {}

        return {
            "last_updated": self.coordinator.last_successful_update_time,
            "panel_info": self.coordinator.panel_info,
        }
