"""Config flow for EVSE Charger."""

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations

from .const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_TYPES,
    DOMAIN,
)
from .options_flow import EVSEEnergyStarOptionsFlow


class EVSEEnergyStarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EVSE Energy Star Config Flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize config flow."""
        self.data: dict[str, Any] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EVSEEnergyStarOptionsFlow:
        """Get options flow."""
        return EVSEEnergyStarOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step user."""
        errors = {}

        if user_input is not None:
            host = user_input.get(CONF_HOST)
            device_name = user_input.get(CONF_DEVICE_NAME, "").strip()

            if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
                errors[CONF_HOST] = "invalid_ip"

            if not device_name:
                errors[CONF_DEVICE_NAME] = "required"

            if not errors:
                translations = await async_get_translations(
                    self.hass, self.hass.config.language, "title"
                )
                title = translations.get(
                    f"component.{DOMAIN}.title", "EVSE Energy Star"
                )

                self.data.update(user_input)

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: self.data[CONF_HOST],
                        CONF_USERNAME: self.data[CONF_USERNAME],
                        CONF_PASSWORD: self.data[CONF_PASSWORD],
                        CONF_DEVICE_TYPE: self.data[CONF_DEVICE_TYPE],
                        CONF_DEVICE_NAME: self.data[CONF_DEVICE_NAME],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default="Eveus Pro"): str,
                    vol.Required(CONF_HOST, default=""): str,
                    vol.Optional(CONF_USERNAME, default=""): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Required(
                        CONF_DEVICE_TYPE, default=DEVICE_TYPES[0]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=DEVICE_TYPES,
                            translation_key=CONF_DEVICE_TYPE,
                            sort=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step reauth."""
        return await self.async_step_user(user_input)
