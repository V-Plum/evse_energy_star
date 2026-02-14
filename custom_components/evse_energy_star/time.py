# time.py
import logging
import aiohttp
import async_timeout
from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
)

LOGGER = logging.getLogger(__name__)

TEXT_DESCRIPTIONS = [
    TextEntityDescription(
        key="startTime",
        translation_key="ha_evse_charger_start_time",
        icon="mdi:clock-time-four-outline"
    ),
    TextEntityDescription(
        key="stopTime",
        translation_key="ha_evse_charger_stop_time",
        icon="mdi:clock-time-four-outline"
    ),
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    slug = hass.data[DOMAIN][entry.entry_id]["device_name_slug"]

    entities = [
        EVSETimeField(entry, host, description, slug)
        for description in TEXT_DESCRIPTIONS
    ]
    async_add_entities(entities)

class EVSETimeField(TextEntity):
    def __init__(self, config_entry: ConfigEntry, host: str, description: TextEntityDescription, slug: str):
        self.config_entry = config_entry
        self._host = host
        self.entity_description = description
        self._key = description.key

        # ✅ Використання перекладу
        self._attr_translation_key = description.translation_key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{description.translation_key}_{config_entry.entry_id}"
        self._attr_native_value = None
        self._attr_min_length = 4
        self._attr_max_length = 5
        self._attr_mode = "text"
        self._attr_suggested_object_id = f"{slug}_{description.translation_key}"

    async def async_update(self):
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"http://{self._host}/init") as resp:
                        data = await resp.json()
                        value = data.get(self._key)
                        if value is not None:
                            self._attr_native_value = str(value)
        except Exception as err:
            LOGGER.warning("time.py → помилка оновлення %s → %s", self._key, err)

    async def async_set_value(self, value: str):
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"http://{self._host}/init") as resp:
                        data = await resp.json()

                    updated = {
                        "startTime": data.get("startTime"),
                        "stopTime":  data.get("stopTime"),
                        "timeZone":  data.get("timeZone"),
                        "isAlarm":   str(data.get("isAlarm")).lower(),
                    }
                    updated[self._key] = value

                    payload = (
                        f"isAlarm={updated['isAlarm']}&"
                        f"startTime={updated['startTime']}&"
                        f"stopTime={updated['stopTime']}&"
                        f"timeZone={updated['timeZone']}"
                    )

                    await session.post(
                        f"http://{self._host}/timer",
                        data=payload,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    self._attr_native_value = value
                    self.async_write_ha_state()
        except Exception as err:
            LOGGER.error("time.py → помилка запису %s = %s → %s", self._key, value, err)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get(CONF_DEVICE_NAME, "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
        }
