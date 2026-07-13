import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN,
    RESTRICTED_MODE_CURRENT,
    UNRESTRICTED_MODE_CURRENT,
)

_LOGGER = logging.getLogger(__name__)

SWITCH_DEFINITIONS = [
    ("groundCtrl", "evse_energy_star_control_pe"),
    ("restrictedMode", "evse_energy_star_restricted_mode"),
]

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        EVSESwitch(coordinator, entry, key, trans_key)
        for key, trans_key in SWITCH_DEFINITIONS
    ]

    entities.append(EVSEScheduleSwitch(coordinator, entry))
    entities.append(EVSESimpleSwitch(coordinator, entry, "oneCharge", "evse_energy_star_one_charge"))
    entities.append(EVSESimpleSwitch(coordinator, entry, "aiMode", "evse_energy_star_adaptive_mode"))

    async_add_entities(entities)

class EVSESwitch(SwitchEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry, key, translation_key):
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._host = coordinator.host
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{translation_key}_{config_entry.entry_id}"
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def is_on(self):
        if self._key == "restrictedMode":
            # СТАН з координатора, а не здогадка "currentSet <= 16".
            # Стара версія виводила режим зі струму, і вимкнути його було
            # неможливо: вимикаєш -> ставиться струм 16 -> "16 <= 16" ->
            # перемикач знову вмикається сам.
            return self.coordinator.restricted_mode
        # effective(): станція застосовує команду із затримкою, і без цього
        # перемикач "вискакував назад" одразу після натискання.
        return bool(self.coordinator.effective(self._key))

    async def async_turn_on(self):
        if self._key == "restrictedMode":
            # Веб-інтерфейс станції при УВІМКНЕННІ режиму ставить 12 А
            # (не 16 — так, це його реальна поведінка) і опускає стелю до 16.
            await self._apply_restricted_mode(True, RESTRICTED_MODE_CURRENT)
        else:
            await self._send_event(True)

    async def async_turn_off(self):
        if self._key == "restrictedMode":
            # При ВИМКНЕННІ веб-інтерфейс ставить 16 А, а стелю піднімає до
            # curDesign. Струм НЕ стрибає одразу на 32 — його піднімає користувач
            # повзунком. Свідомо повторюємо це: самовільно подвоювати струм
            # зарядки від одного кліку перемикача було б небезпечно.
            await self._apply_restricted_mode(False, UNRESTRICTED_MODE_CURRENT)
        else:
            await self._send_event(False)

    async def _apply_restricted_mode(self, restricted: bool, target_current: int):
        """Перемкнути режим обмеження струму.

        На станцію летить ЛИШЕ currentSet — поля restrictedMode в неї немає
        взагалі. Сам режим живе в координаторі, як змінна сторінки у
        веб-інтерфейсі станції.
        """
        # Спершу режим, потім струм: інакше синхронізація в координаторі могла б
        # застати проміжний стан і зробити хибний висновок.
        self.coordinator.set_restricted_mode(restricted)

        if not await self._post("currentSet", target_current):
            return

        self.coordinator.note_write("currentSet", target_current)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _send_event(self, state: bool):
        value = 1 if state else 0
        if await self._post(self._key, value):
            self.coordinator.note_write(self._key, value)
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def _post(self, key: str, value) -> bool:
        payload = f"{key}={value}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "pageEvent": key,
        }
        session = async_get_clientsession(self.coordinator.hass)
        try:
            await session.post(f"http://{self._host}/pageEvent", data=payload, headers=headers)
            return True
        except Exception as err:
            _LOGGER.error("switch.py → помилка запиту %s=%s → %s", key, value, repr(err))
            return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get('device_name', 'Eveus Pro'),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }

class EVSEScheduleSwitch(SwitchEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry):
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._host = coordinator.host
        self._attr_translation_key = "evse_energy_star_schedule"
        self._attr_unique_id = f"schedule_{config_entry.entry_id}"
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def is_on(self):
        value = self.coordinator.effective("isAlarm")
        return str(value).lower() in ["true", "1"]

    async def async_turn_on(self):
        await self._send(True)

    async def async_turn_off(self):
        await self._send(False)

    async def _send(self, state: bool):
        data = self.coordinator.data
        if not data:
            _LOGGER.warning("switch.py → coordinator.data порожній, розклад не оновлено")
            return

        payload = (
            f"isAlarm={'true' if state else 'false'}&"
            f"startTime={data.get('startTime')}&"
            f"stopTime={data.get('stopTime')}&"
            f"timeZone={data.get('timeZone')}"
        )
        session = async_get_clientsession(self.coordinator.hass)
        try:
            await session.post(f"http://{self._host}/timer", data=payload, headers={
                "Content-Type": "application/x-www-form-urlencoded"
            })
            self.coordinator.note_write("isAlarm", "true" if state else "false")
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("switch.py → помилка оновлення розкладу → %s", repr(err))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get('device_name', 'Eveus Pro'),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }

class EVSESimpleSwitch(SwitchEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry, key, translation_key):
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._host = coordinator.host
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{translation_key}_{config_entry.entry_id}"
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def is_on(self):
        # aiMode читається з aiStatus, але ЗАПИСУЄТЬСЯ як aiMode — тому намір
        # памʼятаємо під ключем aiMode, а якщо його немає, дивимось на станцію.
        if self._key == "aiMode":
            pending = self.coordinator.effective("aiMode")
            val = pending if pending is not None else self.coordinator.data.get("aiStatus")
        else:
            val = self.coordinator.effective(self._key)
        return str(val).lower() in ["true", "1"]

    async def async_turn_on(self):
        await self._send(True)

    async def async_turn_off(self):
        await self._send(False)

    async def _send(self, state: bool):
        value = 1 if state else 0
        payload = f"{self._key}={value}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "pageEvent": self._key
        }
        session = async_get_clientsession(self.coordinator.hass)
        try:
            await session.post(f"http://{self._host}/pageEvent", data=payload, headers=headers)
            # Без цього перемикач "вискакував назад": станція застосовує команду
            # із затримкою, і наступне опитування повертало старе значення.
            self.coordinator.note_write(self._key, value)
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("switch.py → помилка запиту %s → %s", self._key, repr(err))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get('device_name', 'Eveus Pro'),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }
