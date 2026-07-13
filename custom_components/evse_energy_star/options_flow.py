from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_VALUE_SCALE,
    DOMAIN,
    VALUE_SCALE_OPTIONS,
)

DEVICE_TYPES = {
    "1_phase": "1_phase",
    "3_phase": "3_phase"
}

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
                vol.Required("host", default=current.get("host", data.get("host", ""))): str,
                vol.Optional("username", default=current.get("username", data.get("username", ""))): str,
                vol.Optional("password", default=current.get("password", data.get("password", ""))): str,
                vol.Required("device_type",
                             default=current.get("device_type", data.get("device_type", "1_phase"))): vol.In(
                    DEVICE_TYPES),
                # Тайм-аут запиту. Було жорстко 5 с — станція, яка "задумалась",
                # роняла ВСІ сутності в unavailable і назад.
                vol.Required("request_timeout",
                             default=current.get("request_timeout", DEFAULT_REQUEST_TIMEOUT)): vol.All(
                    vol.Coerce(int), vol.Range(min=3, max=60)),
                # Масштаб струму та енергії. Типова прошивка віддає десяті
                # (curMeas1=160 -> 16.0 A), але не всі — див. issue #7.
                vol.Required("value_scale",
                             default=current.get("value_scale", DEFAULT_VALUE_SCALE)): vol.In(
                    VALUE_SCALE_OPTIONS),
            }),
        )

def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return EVSEEnergyStarOptionsFlow(config_entry)