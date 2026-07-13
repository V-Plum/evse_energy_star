"""Бінарні сенсори станції.

Наразі один: наявність заземлення в розетці.

Чому саме binary_sensor, а не sensor: відсутнє заземлення — це НЕ статус, це
небезпека. `device_class: SAFETY` дає Home Assistant зрозуміти це: сутність
підхоплюється картками "Проблеми", має автоматичну іконку й переклад, і в
автоматизації достатньо `to: "on"` замість порівняння рядків.

Семантика SAFETY інвертована і це навмисно (так визначено в Home Assistant):
    on  = НЕБЕЗПЕЧНО -> заземлення НЕМАЄ
    off = безпечно   -> заземлення Є
"""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EVSEGroundBinarySensor(coordinator, entry)])


class EVSEGroundBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Заземлення в розетці. on = немає заземлення (небезпечно)."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry

        self._attr_translation_key = "evse_energy_star_ground"
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = (
            f"{coordinator.device_name_slug}_{self._attr_translation_key}"
        )
        self._attr_unique_id = f"ground_binary_{config_entry.entry_id}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """True = НЕБЕЗПЕЧНО (заземлення немає)."""
        value = self.coordinator.data.get("ground")
        if value is None:
            return None
        return not bool(value)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get("device_name", "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion"),
        }
