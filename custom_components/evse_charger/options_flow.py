"""Options flow for EVSE Charger."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_TYPES,
)


class EVSEEnergyStarOptionsFlow(config_entries.OptionsFlow):
    """EVSE Energy Star Options Flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Step init."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=current.get(CONF_HOST, data.get(CONF_HOST, "")),
                    ): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=current.get(CONF_USERNAME, data.get(CONF_USERNAME, "")),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=current.get(CONF_PASSWORD, data.get(CONF_PASSWORD, "")),
                    ): str,
                    vol.Required(
                        CONF_DEVICE_TYPE,
                        default=current.get(
                            CONF_DEVICE_TYPE,
                            data.get(CONF_DEVICE_TYPE, DEVICE_TYPES[0]),
                        ),
                    ): vol.In(DEVICE_TYPES),
                }
            ),
        )


def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> EVSEEnergyStarOptionsFlow:
    """Get options flow."""
    return EVSEEnergyStarOptionsFlow(config_entry)
