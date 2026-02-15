"""Time entity for EVSE Charger."""

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_NAME,
    DOMAIN,
)
from .coordinator import EVSECoordinator

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
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    slug = hass.data[DOMAIN][entry.entry_id]["device_name_slug"]

    entities = [
        EVSETimeField(coordinator, entry, description, slug)
        for description in TEXT_DESCRIPTIONS
    ]
    async_add_entities(entities)


class EVSETimeField(CoordinatorEntity, TextEntity):
    """EVSE Time Field."""

    def __init__(
        self,
        coordinator: EVSECoordinator,
        config_entry: ConfigEntry,
        description: TextEntityDescription,
        slug: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
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

    @property
    def available(self) -> bool:
        """Return true if the text entity is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str | None:
        """Return native value from coordinator data."""
        value = self.coordinator.data.get(self._key)
        return str(value) if value is not None else None

    async def async_set_value(self, value: str) -> None:
        """Set value."""
        try:
            data = dict(self.coordinator.data)
            updated = {
                "startTime": data.get("startTime", "00:00"),
                "stopTime": data.get("stopTime", "00:00"),
                "timeZone": data.get("timeZone", 0),
                "isAlarm": str(data.get("isAlarm", "false")).lower(),
            }
            updated[self._key] = value

            payload = (
                f"isAlarm={updated['isAlarm']}&"
                f"startTime={updated['startTime']}&"
                f"stopTime={updated['stopTime']}&"
                f"timeZone={updated['timeZone']}"
            )

            session = async_get_clientsession(self.coordinator.hass)
            await session.post(
                f"http://{self.coordinator.host}/timer",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            await self.coordinator.async_request_refresh()
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
