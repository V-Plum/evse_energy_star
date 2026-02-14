import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
)

LOGGER = logging.getLogger(__name__)

SWITCH_DEFINITIONS = [
    ("groundCtrl", "ha_evse_charger_control_pe"),
    ("restrictedMode", "ha_evse_charger_restricted_mode"),
    ("evseEnabled", "ha_evse_charger_evse_enabled"),
]

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        EVSESwitch(coordinator, entry, key, trans_key)
        for key, trans_key in SWITCH_DEFINITIONS
    ]

    entities.append(EVSEScheduleSwitch(coordinator, entry))
    entities.append(EVSESimpleSwitch(coordinator, entry, "oneCharge", "ha_evse_charger_one_charge"))
    entities.append(EVSESimpleSwitch(coordinator, entry, "aiMode", "ha_evse_charger_adaptive_mode"))

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
            return float(self.coordinator.data.get("currentSet", 32)) <= 16
        return bool(self.coordinator.data.get(self._key))

    async def async_turn_on(self):
        if self._key == "restrictedMode":
            await self._set_current_if_needed(12, only_if_high=True)
        else:
            await self._send_event(True)

    async def async_turn_off(self):
        if self._key == "restrictedMode":
            await self._set_current_if_needed(16, only_if_low=True)
        else:
            await self._send_event(False)

    async def _send_event(self, state: bool):
        payload = f"{self._key}={'1' if state else '0'}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "pageEvent": self._key
        }
        session = async_get_clientsession(self.coordinator.hass)
        try:
            await session.post(f"http://{self._host}/pageEvent", data=payload, headers=headers)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            LOGGER.error("switch.py → помилка запиту %s → %s", self._key, repr(err))

    async def _set_current_if_needed(self, target, only_if_high=False, only_if_low=False):
        current = float(self.coordinator.data.get("currentSet", 32))
        if (only_if_high and current > target) or (only_if_low and current <= target):
            payload = f"currentSet={target}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "pageEvent": "currentSet"
            }
            session = async_get_clientsession(self.coordinator.hass)
            await session.post(f"http://{self._host}/pageEvent", data=payload, headers=headers)
            await self.coordinator.async_request_refresh()

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
        self._attr_translation_key = "ha_evse_charger_schedule"
        self._attr_unique_id = f"schedule_{config_entry.entry_id}"
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def is_on(self):
        value = self.coordinator.data.get("isAlarm")
        return str(value).lower() in ["true", "1"]

    async def async_turn_on(self):
        await self._send(True)

    async def async_turn_off(self):
        await self._send(False)

    async def _send(self, state: bool):
        data = self.coordinator.data
        if not data:
            LOGGER.warning("switch.py → coordinator.data порожній, розклад не оновлено")
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
            await self.coordinator.async_request_refresh()
        except Exception as err:
            LOGGER.error("switch.py → помилка оновлення розкладу → %s", repr(err))

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
        if self._key == "aiMode":
            val = self.coordinator.data.get("aiStatus")
        else:
            val = self.coordinator.data.get(self._key)
        return str(val).lower() in ["true", "1"]

    async def async_turn_on(self):
        await self._send(True)

    async def async_turn_off(self):
        await self._send(False)

    async def _send(self, state: bool):
        payload = f"{self._key}={'1' if state else '0'}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "pageEvent": self._key
        }
        session = async_get_clientsession(self.coordinator.hass)
        try:
            await session.post(f"http://{self._host}/pageEvent", data=payload, headers=headers)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            LOGGER.error("switch.py → помилка запиту %s → %s", self._key, repr(err))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get(CONF_DEVICE_NAME, 'Eveus Pro'),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }
