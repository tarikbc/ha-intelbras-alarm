"""Support for Intelbras Alarm Control Panel."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
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
    """Set up Intelbras alarm control panel from a config entry."""
    coordinator: IntelbrasAlarmCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    async_add_entities([IntelbrasAlarmControlPanel(coordinator)])


class IntelbrasAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of an Intelbras alarm control panel."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    # No user code required - authentication handled at connection level
    _attr_code_arm_required = False
    _attr_code_disarm_required = False

    def __init__(self, coordinator: IntelbrasAlarmCoordinator) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self.coordinator: IntelbrasAlarmCoordinator = coordinator
        
        # Set unique ID
        device_id = list(coordinator.device_identifiers)[0][1]
        self._attr_unique_id = f"{device_id}_alarm_panel"
        
        # Set device info
        self._attr_device_info = coordinator.device_info

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm control panel."""
        if not self.coordinator.last_update_success:
            return None
            
        # Check if connection is disabled
        if (self.coordinator.data and 
            self.coordinator.data.get("status", {}).get("connection_disabled", False)):
            return None
            
        alarm_status = self.coordinator.get_alarm_status()
        
        # Handle None values when disconnected
        if alarm_status["alarm"] is True:
            return AlarmControlPanelState.TRIGGERED
        elif alarm_status["armed"] is True:
            return AlarmControlPanelState.ARMED_AWAY
        elif alarm_status["partial_armed"] is True:
            return AlarmControlPanelState.ARMED_HOME
        elif alarm_status["armed"] is False:
            return AlarmControlPanelState.DISARMED
        else:
            return None  # Unknown state when values are None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
            
        status = self.coordinator.data.get("status", {})
        
        attributes = {
            "armed": status.get("armed", False),
            "partial_armed": status.get("partial_armed", False),
            "alarm": status.get("alarm", False),
            "panel_info": self.coordinator.panel_info,
        }
        
        # Add zone information
        zones = status.get("zones", [])
        active_zones = [zone["name"] for zone in zones if zone.get("active")]
        bypassed_zones = [zone["name"] for zone in zones if zone.get("bypassed")]
        alarm_zones = [zone["name"] for zone in zones if zone.get("alarm")]
        
        if active_zones:
            attributes["active_zones"] = active_zones
        if bypassed_zones:
            attributes["bypassed_zones"] = bypassed_zones
        if alarm_zones:
            attributes["alarm_zones"] = alarm_zones
            
        # Add recent events
        events = self.coordinator.get_events(3)
        if events:
            attributes["recent_events"] = [
                {
                    "description": event.get("description", "Unknown event"),
                    "timestamp": event.get("timestamp", "Unknown"),
                    "type": event.get("type", "unknown"),
                }
                for event in events
            ]
        
        return attributes

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.debug("Disarming alarm panel")
        success = await self.coordinator.async_disarm()
        if not success:
            _LOGGER.error("Failed to disarm alarm panel")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.debug("Arming alarm panel (away)")
        success = await self.coordinator.async_arm("away")
        if not success:
            _LOGGER.error("Failed to arm alarm panel (away)")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        _LOGGER.debug("Arming alarm panel (home)")
        success = await self.coordinator.async_arm("home")
        if not success:
            _LOGGER.error("Failed to arm alarm panel (home)")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is unavailable when connection is disabled
        if (self.coordinator.data and 
            self.coordinator.data.get("status", {}).get("connection_disabled", False)):
            return False
            
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        ) 