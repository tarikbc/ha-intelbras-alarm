"""The Intelbras Alarm integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IntelbrasAlarmCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intelbras Alarm from a config entry."""
    coordinator = IntelbrasAlarmCoordinator(hass, entry)

    try:
        # Use a shorter timeout for initial refresh to avoid cancellation issues
        await asyncio.wait_for(
            coordinator.async_config_entry_first_refresh(),
            timeout=30  # 30 second timeout for initial setup
        )
    except asyncio.TimeoutError:
        _LOGGER.warning("Initial connection timeout - integration will continue loading and retry automatically")
        # Don't return False - let the integration start with a timeout, it will retry
    except asyncio.CancelledError:
        _LOGGER.warning("Setup was cancelled - integration will retry connection automatically")
        # Don't return False - let the integration start even if cancelled
    except Exception as ex:
        _LOGGER.error("Failed to initialize Intelbras Alarm: %s", ex)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: IntelbrasAlarmCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
