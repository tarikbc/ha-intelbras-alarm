"""Config flow for Intelbras Alarm integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_PANEL_IP,
    DEFAULT_PORT,
    DOMAIN,
)
from .protocol import IntelbrasConnector

_LOGGER = logging.getLogger(__name__)


def validate_and_clean_password(password: str) -> str:
    """Validate and clean remote password format."""
    # Remove any spaces or formatting
    clean_password = password.strip().replace(" ", "").replace("-", "")

    # Must be 4-6 digits
    if not re.match(r"^[0-9A-Fa-f]{4,6}$", clean_password):
        raise vol.Invalid("Remote password must be 4-6 digits (e.g., 1234, 878787)")

    return clean_password.upper()


# Use proper voluptuous validators that can be serialized
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PANEL_IP): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Intelbras Alarm."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "panel_ip_example": "192.168.1.100",
                    "password_example": "878787",
                },
            )

        # Validate and clean input data
        try:
            # Validate IP address format
            ip_address = user_input[CONF_PANEL_IP].strip()
            if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", ip_address):
                errors[CONF_PANEL_IP] = "panel_ip"

            # Validate and clean password
            try:
                clean_password = validate_and_clean_password(user_input[CONF_PASSWORD])
                user_input[CONF_PASSWORD] = clean_password  # Use cleaned version
            except vol.Invalid:
                errors[CONF_PASSWORD] = "password"

            # If validation failed, show form again with errors
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                    description_placeholders={
                        "panel_ip_example": "192.168.1.100",
                        "password_example": "878787",
                    },
                )

        except Exception as ex:
            _LOGGER.error("Input validation error: %s", ex)
            errors["base"] = "unknown"

        # Test connection with improved error handling
        if not errors:
            try:
                _LOGGER.info("Testing connection to panel at %s:%s", user_input[CONF_PANEL_IP], user_input[CONF_PORT])
                await self._test_connection(user_input)
                _LOGGER.info("Connection test successful")

            except CannotConnect as ex:
                _LOGGER.warning("Connection failed: %s", ex)
                errors["base"] = "cannot_connect"
            except InvalidAuth as ex:
                _LOGGER.warning("Authentication failed: %s", ex)
                errors["base"] = "invalid_auth"
            except Exception as ex:
                _LOGGER.exception("Unexpected exception during connection test: %s", ex)
                errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "panel_ip_example": "192.168.1.100",
                    "password_example": "878787",
                },
            )

        # Use IP as unique ID
        unique_id = user_input[CONF_PANEL_IP].replace(".", "_")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        title = f"Intelbras Panel ({user_input[CONF_PANEL_IP]})"

        return self.async_create_entry(title=title, data=user_input)

    async def _test_connection(self, config: dict[str, Any]) -> None:
        """Test if we can connect to the panel with improved error handling."""
        connector = IntelbrasConnector(config)
        try:
            # Test basic connection first
            _LOGGER.debug(
                "Testing basic connection to %s:%s", config[CONF_PANEL_IP], config.get(CONF_PORT, DEFAULT_PORT)
            )

            success = await connector.async_connect()
            if not success:
                error_msg = connector.get_last_connection_error()
                _LOGGER.error("Connection failed: %s", error_msg)
                raise CannotConnect(f"Connection failed: {error_msg}")

            _LOGGER.debug("Basic connection successful, testing authentication")

            # Test authentication with proper sequence
            auth_success = await connector.async_authenticate()
            if not auth_success:
                _LOGGER.error("Authentication failed - check Remote Password")
                raise InvalidAuth("Authentication failed - verify Remote Password in panel settings")

            _LOGGER.debug("Authentication successful")

        except CannotConnect:
            raise  # Re-raise connection errors as-is
        except InvalidAuth:
            raise  # Re-raise auth errors as-is
        except Exception as ex:
            _LOGGER.error("Unexpected error during connection test: %s", ex)
            raise CannotConnect(f"Unexpected error: {ex}")
        finally:
            # Always clean up the connection
            try:
                await connector.async_disconnect()
            except Exception as ex:
                _LOGGER.warning("Error during disconnect: %s", ex)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
