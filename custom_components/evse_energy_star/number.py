import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

NUMBER_DEFINITIONS = [
    {
        "key": "currentSet",
        "id": "ha_evse_charger_current_limit",
        "icon": "mdi:current-dc",
        "min": 6,
        "max": 32,
        "step": 1,
        "unit": "A"
    },
    {
        "key": "aiVoltage",
        "id": "ha_evse_charger_voltage_adaptive",
        "icon": "mdi:flash-outline",
        "min": 180,
        "max": 240,
        "step": 1,
        "unit": "V"
    }
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        EVSENumber(coordinator, entry, definition)
        for definition in NUMBER_DEFINITIONS
    ]
    async_add_entities(entities)

class EVSENumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry, config):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._host = coordinator.host
        self._key = config["key"]
        self._translation_key = config["id"]
        self._config = config
        self._attr_translation_key = self._translation_key
        self._attr_icon = config["icon"]
        self._attr_native_unit_of_measurement = config["unit"]
        self._attr_native_step = config["step"]
        self._attr_native_min_value = config["min"]
        self._attr_unique_id = f"{self._translation_key}_{config_entry.entry_id}"
        self._restricted_mode = False
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        return float(value) if value is not None else None

    @property
    def native_max_value(self):
        if self._key == "currentSet":
            current = self.coordinator.data.get("currentSet")
            if current is not None:
                self._restricted_mode = float(current) <= 16
            design_max = float(self.coordinator.data.get("curDesign", 32))
            return 16 if self._restricted_mode else design_max
        return self._config["max"]

    async def async_set_native_value(self, value: float):
        payload = f"{self._key}={value}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "pageEvent": self._key
        }

        try:
            session = async_get_clientsession(self.coordinator.hass)
            await session.post(
                f"http://{self._host}/pageEvent",
                data=payload,
                headers=headers
            )
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except Exception as err:
            LOGGER.error("number.py → помилка запису %s = %s → %s", self._key, value, repr(err))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get("device_name", "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }
