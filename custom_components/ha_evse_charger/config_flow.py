from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DOMAIN,
    DEVICE_TYPES,
    CONF_HOST,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_UPDATE_RATE,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from .options_flow import EVSEEnergyStarOptionsFlow
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations
import re

class EVSEEnergyStarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EVSE Energy Star Config Flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    def async_get_options_flow(config_entry):
        return EVSEEnergyStarOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
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
                    self.hass,
                    self.hass.config.language,
                    "title"
                )
                title = translations.get(
                    f"component.{DOMAIN}.title",
                    "EVSE Energy Star"
                )

                self.data.update(user_input)
                
                return self.async_create_entry(
                    title = title,
                    data = {
                        CONF_HOST: self.data[CONF_HOST],
                        CONF_USERNAME: self.data[CONF_USERNAME],
                        CONF_PASSWORD: self.data[CONF_PASSWORD],
                        CONF_DEVICE_TYPE: self.data[CONF_DEVICE_TYPE],
                        CONF_DEVICE_NAME: self.data[CONF_DEVICE_NAME],
                        "integration_title": integration_title
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_NAME, default="Eveus Pro"): str,
                vol.Required(CONF_HOST, default=""): str,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPES[0]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DEVICE_TYPES,
                        translation_key=CONF_DEVICE_TYPE,
                        sort=True,
                    )
                ),
            }),
            errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        return await self.async_step_user(user_input)
