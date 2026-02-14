"""Sensor entity for EVSE Charger."""

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    DOMAIN,
    STATUS_MAP,
)
from .coordinator import EVSECoordinator

LOGGER = logging.getLogger(__name__)

SENSOR_DEFINITIONS = [
    ("state", "evse_charger_status", None, None, None, None),
    (
        "currentSet",
        "evse_charger_current_set",
        "A",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.CURRENT,
        None,
    ),
    (
        "curMeas1",
        "evse_charger_current_phase_1",
        "A",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.CURRENT,
        None,
    ),
    (
        "voltMeas1",
        "evse_charger_voltage_phase_1",
        "V",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.VOLTAGE,
        None,
    ),
    (
        "temperature1",
        "evse_charger_temperature_box",
        "°C",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "temperature2",
        "evse_charger_temperature_socket",
        "°C",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "leakValue",
        "evse_charger_leakage",
        "mA",
        SensorStateClass.MEASUREMENT,
        None,
        None,
    ),
    (
        "sessionEnergy",
        "evse_charger_session_energy",
        "kWh",
        SensorStateClass.TOTAL_INCREASING,
        SensorDeviceClass.ENERGY,
        None,
    ),
    (
        "sessionTime",
        "evse_charger_session_time",
        UnitOfTime.SECONDS,
        None,
        SensorDeviceClass.DURATION,
        None,
    ),
    (
        "totalEnergy",
        "evse_charger_total_energy",
        "kWh",
        SensorStateClass.TOTAL_INCREASING,
        SensorDeviceClass.ENERGY,
        None,
    ),
    (
        "systemTime",
        "evse_charger_system_time",
        None,
        None,
        SensorDeviceClass.TIMESTAMP,
        None,
    ),
    (
        "powerMeas",
        "evse_charger_power",
        "kW",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.POWER,
        None,
    ),
]

THREE_PHASE_SENSORS = [
    (
        "curMeas2",
        "evse_charger_current_phase_2",
        "A",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.CURRENT,
        None,
    ),
    (
        "curMeas3",
        "evse_charger_current_phase_3",
        "A",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.CURRENT,
        None,
    ),
    (
        "voltMeas2",
        "evse_charger_voltage_phase_2",
        "V",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.VOLTAGE,
        None,
    ),
    (
        "voltMeas3",
        "evse_charger_voltage_phase_3",
        "V",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.VOLTAGE,
        None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Define setup entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    device_type = entry.options.get(
        CONF_DEVICE_TYPE, entry.data.get(CONF_DEVICE_TYPE, "1_phase")
    )

    entities = [
        EVSESensor(coordinator, entry, key, trans_key, unit, state_class, device_class)
        for key, trans_key, unit, state_class, device_class, _ in SENSOR_DEFINITIONS
    ]

    if device_type == "3_phase":
        entities += [
            EVSESensor(
                coordinator,
                entry,
                key,
                trans_key,
                unit,
                state_class,
                device_class,
            )
            for key, trans_key, unit, state_class, device_class, _ in THREE_PHASE_SENSORS  # noqa: E501
        ]

    entities.append(EVSEGroundStatus(coordinator, entry))
    async_add_entities(entities)


class EVSESensor(CoordinatorEntity, SensorEntity):
    """EVSE Sensor."""

    def __init__(
        self,
        coordinator: EVSECoordinator,
        config_entry: ConfigEntry,
        key: str,
        translation_key: str,
        unit: str | None,
        state_class: SensorStateClass | None,
        device_class: SensorDeviceClass | None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class

        self._attr_has_entity_name = True
        self._attr_suggested_object_id = (
            f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        )
        self._attr_unique_id = f"{translation_key}_{config_entry.entry_id}"

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return "unknown"
        try:
            if self._key in ["curMeas1", "curMeas2", "curMeas3"]:
                return round(float(value), 2)
            if self._key in ["sessionEnergy", "totalEnergy"]:
                return round(float(value), 3)
            if self._key == "sessionTime":
                # Device reports elapsed charging time in seconds.
                return int(float(str(value)))
            if self._key == "systemTime":
                new_ts = int(float(str(value)))
                return datetime.fromtimestamp(new_ts, tz=UTC)
            if self._key == "state":
                return STATUS_MAP.get(value, "unknown")
            return value  # noqa: TRY300
        except Exception:
            LOGGER.exception("[sensor] error processing %s", self._key)
            return str(value)

    def _handle_coordinator_update(self) -> None:
        new_value = self.coordinator.data.get(self._key)
        if self._key == "systemTime":
            try:
                old_ts = int(float(str(self._attr_native_value or "0")))
                new_ts = int(float(str(new_value)))
                old_dt = datetime.fromtimestamp(old_ts, tz=UTC)
                new_dt = datetime.fromtimestamp(new_ts, tz=UTC)
                if abs((new_dt - old_dt).total_seconds()) <= 2:
                    return
            except Exception:
                LOGGER.exception("[sensor] systemTime comparison error")

        self._attr_native_value = new_value
        self.async_write_ha_state()

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get(CONF_DEVICE_NAME, "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion"),
        }


class EVSEGroundStatus(CoordinatorEntity, SensorEntity):
    """EVSE Ground Status."""

    def __init__(
        self,
        coordinator: EVSECoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_translation_key = "evse_charger_ground_status"

        self._attr_has_entity_name = True
        self._attr_suggested_object_id = (
            f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        )
        self._attr_unique_id = f"ground_status_{config_entry.entry_id}"

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        return "✅" if bool(self.coordinator.data.get("ground", 0)) else "❌"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return (
            "mdi:checkbox-marked-circle"
            if self.native_value == "✅"
            else "mdi:close-circle-outline"
        )

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.data.get(CONF_DEVICE_NAME, "Eveus Pro"),
            "manufacturer": "Energy Star",
            "model": "EVSE",
            "sw_version": self.coordinator.data.get("fwVersion"),
        }
