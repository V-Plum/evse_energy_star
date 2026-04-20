import logging
from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from .const import DOMAIN, STATUS_MAP

_LOGGER = logging.getLogger(__name__)

SENSOR_DEFINITIONS = [
    ("state", "evse_energy_star_status", None, None, None, None),
    ("currentSet", "evse_energy_star_current_set", "A", SensorStateClass.MEASUREMENT, SensorDeviceClass.CURRENT, None),
    ("curMeas1", "evse_energy_star_current_phase_1", "A", SensorStateClass.MEASUREMENT, SensorDeviceClass.CURRENT, None),
    ("voltMeas1", "evse_energy_star_voltage_phase_1", "V", SensorStateClass.MEASUREMENT, SensorDeviceClass.VOLTAGE, None),
    ("temperature1", "evse_energy_star_temperature_box", "°C", SensorStateClass.MEASUREMENT, SensorDeviceClass.TEMPERATURE, None),
    ("temperature2", "evse_energy_star_temperature_socket", "°C", SensorStateClass.MEASUREMENT, SensorDeviceClass.TEMPERATURE, None),
    ("leakValue", "evse_energy_star_leakage", "мА", SensorStateClass.MEASUREMENT, None, None),
    ("sessionEnergy", "evse_energy_star_session_energy", "kWh", SensorStateClass.TOTAL_INCREASING, SensorDeviceClass.ENERGY, None),
    ("sessionTime", "evse_energy_star_session_time", None, None, None, None),
    ("totalEnergy", "evse_energy_star_total_energy", "kWh", SensorStateClass.TOTAL_INCREASING, SensorDeviceClass.ENERGY, None),
    ("systemTime", "evse_energy_star_system_time", None, None, None, None),
]

THREE_PHASE_SENSORS = [
    ("curMeas2", "evse_energy_star_current_phase_2", "A", SensorStateClass.MEASUREMENT, SensorDeviceClass.CURRENT, None),
    ("curMeas3", "evse_energy_star_current_phase_3", "A", SensorStateClass.MEASUREMENT, SensorDeviceClass.CURRENT, None),
    ("voltMeas2", "evse_energy_star_voltage_phase_2", "V", SensorStateClass.MEASUREMENT, SensorDeviceClass.VOLTAGE, None),
    ("voltMeas3", "evse_energy_star_voltage_phase_3", "V", SensorStateClass.MEASUREMENT, SensorDeviceClass.VOLTAGE, None),
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    device_type = entry.options.get("device_type", entry.data.get("device_type", "1_phase"))

    entities = [
        EVSESensor(coordinator, entry, key, trans_key, unit, state_class, device_class)
        for key, trans_key, unit, state_class, device_class, _ in SENSOR_DEFINITIONS
    ]

    if device_type == "3_phase":
        entities += [
            EVSESensor(coordinator, entry, key, trans_key, unit, state_class, device_class)
            for key, trans_key, unit, state_class, device_class, _ in THREE_PHASE_SENSORS
        ]

    entities.append(EVSEGroundStatus(coordinator, entry))
    async_add_entities(entities)

class EVSESensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry, key, translation_key, unit, state_class, device_class):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class

        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        self._attr_unique_id = f"{translation_key}_{config_entry.entry_id}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        try:
            if self._key == "curMeas1":
                return round(float(value), 2)
            if self._key in ["sessionEnergy", "totalEnergy"]:
                return round(float(value), 3)
            if self._key == "sessionTime":
                total_sec = int(float(value))
                h = total_sec // 3600
                m = (total_sec % 3600) // 60
                s = total_sec % 60
                return f"{h:02}:{m:02}:{s:02}"
            if self._key == "state":
                # Повертаємо ключ для перекладу з translations
                return STATUS_MAP.get(value, "unknown")
            return value
        except Exception as err:
            _LOGGER.warning("sensor.py → помилка в обробці %s: %s", self._key, repr(err))
            return str(value)

    def _handle_coordinator_update(self):
        new_value = self.coordinator.data.get(self._key)
        if self._key == "systemTime":
            try:
                old_str = str(self._attr_native_value)
                new_str = str(new_value)
                fmt = "%H:%M:%S"
                old_dt = datetime.strptime(old_str, fmt)
                new_dt = datetime.strptime(new_str, fmt)
                if abs((new_dt - old_dt).total_seconds()) <= 2:
                    return
            except Exception as err:
                _LOGGER.debug("sensor.py → systemTime порівняння: %s", repr(err))

        self._attr_native_value = new_value
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get("device_name", "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }

class EVSEGroundStatus(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_translation_key = "evse_energy_star_ground_status"

        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        self._attr_unique_id = f"ground_status_{config_entry.entry_id}"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        return "✅" if bool(self.coordinator.data.get("ground", 0)) else "❌"

    @property
    def icon(self):
        return "mdi:checkbox-marked-circle" if self.native_value == "✅" else "mdi:close-circle-outline"

    def _handle_coordinator_update(self):
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get("device_name", "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion")
        }
