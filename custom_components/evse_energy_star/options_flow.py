from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DOMAIN
    DEVICE_TYPES,
    CONF_HOST,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    DEVICE_TYPES,
    CONF_UPDATE_RATE,
    CONF_USERNAME,
    CONF_PASSWORD,
)

class EVSEEnergyStarOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, data.get(CONF_HOST, ""))): str,
                vol.Optional(CONF_USERNAME, default=current.get(CONF_USERNAME, data.get(CONF_USERNAME, ""))): str,
                vol.Optional(CONF_PASSWORD, default=current.get(CONF_PASSWORD, data.get(CONF_PASSWORD, ""))): str,
                vol.Required(CONF_DEVICE_TYPE,
                             default=current.get(CONF_DEVICE_TYPE, data.get(CONF_DEVICE_TYPE, DEVICE_TYPES[0]))): vol.In(
                    DEVICE_TYPES),
            }),
        )

def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return EVSEEnergyStarOptionsFlow(config_entry)
