import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN,
    FALLBACK_DESIGN_CURRENT,
    RESTRICTED_MODE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

NUMBER_DEFINITIONS = [
    {
        "key": "currentSet",
        "id": "evse_energy_star_current_limit",
        "icon": "mdi:current-dc",
        "min": 6,
        "max": 32,
        "step": 1,
        "unit": "A"
    },
    {
        "key": "aiVoltage",
        "id": "evse_energy_star_voltage_adaptive",
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
        # effective(), а не data.get(): одразу після запису станція ще секунду-дві
        # віддає старе значення, і повзунок стрибав би назад.
        value = self.coordinator.effective(self._key)
        return float(value) if value is not None else None

    @property
    def native_max_value(self):
        """Стеля струму.

        Раніше тут режим обмеження ВИВОДИВСЯ зі струму на кожному звертанні:

            self._restricted_mode = float(current) <= 16
            return 16 if self._restricted_mode else design_max

        Через це виникало замкнене коло. Вимкнув режим -> веб-логіка ставить
        струм 16 -> "16 <= 16, отже режим увімкнено" -> стеля знову 16 ->
        підняти повзунок вище 16 неможливо взагалі. Саме тому рідний веб-інтерфейс
        "працював краще".

        Тепер режим — це СТАН у координаторі (як змінна сторінки у веб-інтерфейсі),
        а не здогадка за струмом. Стеля береться зі станції: curDesign.
        """
        if self._key == "currentSet":
            if self.coordinator.restricted_mode:
                return float(RESTRICTED_MODE_LIMIT)
            design_max = self.coordinator.effective("curDesign", FALLBACK_DESIGN_CURRENT)
            try:
                return float(design_max)
            except (TypeError, ValueError):
                return float(FALLBACK_DESIGN_CURRENT)
        return self._config["max"]

    async def async_set_native_value(self, value: float):
        # Станція приймає цілі ампери; 16.0 у payload вона не зрозуміє так, як 16.
        payload_value = int(value) if float(value).is_integer() else value
        payload = f"{self._key}={payload_value}"
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
            # Памʼятаємо намір: наступні 1-2 відповіді /main ще міститимуть старе
            # значення (станція застосовує команду із затримкою).
            self.coordinator.note_write(self._key, payload_value)

            # Підняли струм вище межі -> обмежений режим знято. Рівно так само
            # чинить веб-інтерфейс станції при оновленні даних.
            if self._key == "currentSet" and float(value) > RESTRICTED_MODE_LIMIT:
                self.coordinator.set_restricted_mode(False)

            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("number.py → помилка запису %s = %s → %s", self._key, value, repr(err))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get("device_name", "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }
