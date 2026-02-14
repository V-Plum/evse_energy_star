"""Time entity for EVSE Charger."""

import logging
from typing import Any

import aiohttp
import async_timeout
from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_NAME,
    CONF_HOST,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)

TEXT_DESCRIPTIONS = [
    TextEntityDescription(
        key="startTime",
        translation_key="evse_charger_start_time",
        icon="mdi:clock-time-four-outline",
    ),
    TextEntityDescription(
        key="stopTime",
        translation_key="evse_charger_stop_time",
        icon="mdi:clock-time-four-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Define setup entry."""
    host = hass.data[DOMAIN][entry.entry_id][CONF_HOST]
    slug = hass.data[DOMAIN][entry.entry_id]["device_name_slug"]

    entities = [
        EVSETimeField(entry, host, description, slug)
        for description in TEXT_DESCRIPTIONS
    ]
    async_add_entities(entities)


class EVSETimeField(TextEntity):
    """EVSE Time Field."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        host: str,
        description: TextEntityDescription,
        slug: str,
    ) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self._host = host
        self.entity_description = description
        self._key = description.key

        self._attr_translation_key = description.translation_key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{description.translation_key}_{config_entry.entry_id}"
        self._attr_native_value = None
        self._attr_min_length = 4
        self._attr_max_length = 5
        self._attr_mode = "text"
        self._attr_suggested_object_id = f"{slug}_{description.translation_key}"

    async def async_update(self) -> None:
        """Update."""
        try:
            async with (
                async_timeout.timeout(5),
                aiohttp.ClientSession() as session,
                session.post(f"http://{self._host}/init") as resp,
            ):
                data = await resp.json()
                value = data.get(self._key)
                if value is not None:
                    self._attr_native_value = str(value)
        except Exception:
            LOGGER.exception("[time] error on getting update %s", self._key)

    async def async_set_value(self, value: str) -> None:
        """Set value."""
        try:
            async with (
                async_timeout.timeout(5),
                aiohttp.ClientSession() as session,
                session.post(f"http://{self._host}/init") as resp,
            ):
                data = await resp.json()

                updated = {
                    "startTime": data.get("startTime"),
                    "stopTime": data.get("stopTime"),
                    "timeZone": data.get("timeZone"),
                    "isAlarm": str(data.get("isAlarm")).lower(),
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
        except Exception:
            LOGGER.exception("[time] error writing %s = %s", self._key, value)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get(CONF_DEVICE_NAME, "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
        }
