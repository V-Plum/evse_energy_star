"""Select entity for EVSE Charger."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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

TIMEZONE_OPTIONS = [str(i) for i in range(-12, 13)]
UPDATE_RATE_OPTIONS = [str(i) for i in [1, 2, 5, 10, 15, 30, 60]]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Define setup entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [TimeZoneSelect(coordinator, entry), UpdateRateSelect(hass, coordinator, entry)]
    )


class TimeZoneSelect(CoordinatorEntity, SelectEntity):
    """Time zone select entity for EVSE Charger."""

    def __init__(self, coordinator: EVSECoordinator, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_translation_key = "time_zone"
        self.entity_description = SelectEntityDescription(
            key="time_zone", translation_key="time_zone", icon="mdi:map-clock-outline"
        )
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = (
            f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        )

        self._attr_unique_id = f"time_zone_{config_entry.entry_id}"
        self._attr_options = TIMEZONE_OPTIONS
        self._attr_current_option = None

        raw = self.coordinator.data.get("timeZone", "0")
        try:
            tz_int = int(float(str(raw).strip()))
            tz_str = str(tz_int)
        except Exception:
            LOGGER.exception("select.py → error converting timeZone: '%s'", raw)
            tz_str = "0"

        if tz_str in self._attr_options:
            self._attr_current_option = tz_str
            LOGGER.debug(
                "select.py → timeZone from /init: %s (%s)", tz_str, type(raw).__name__
            )
        else:
            self._attr_current_option = None
            LOGGER.warning("select.py → invalid timeZone from /init: '%s'", raw)

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        session = async_get_clientsession(self.coordinator.hass)
        payload = f"isAlarm=false&startTime=None&stopTime=None&timeZone={option}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            await session.post(
                f"http://{self.coordinator.host}/timer", data=payload, headers=headers
            )
            self._attr_current_option = option
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
            LOGGER.debug("select.py → timeZone changed to %s through /timer", option)
        except Exception:
            LOGGER.exception("select.py → error requesting /timer: timeZone=%s", option)

    @property
    def available(self) -> bool:
        """Return true if the select is available."""
        return self.coordinator.last_update_success

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


class UpdateRateSelect(SelectEntity):
    """Update rate select entity for EVSE Charger."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EVSECoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_translation_key = "refresh_rate"
        self.entity_description = SelectEntityDescription(
            key="refresh_rate", translation_key="refresh_rate", icon="mdi:history"
        )
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = (
            f"{self.coordinator.device_name_slug}_{self._attr_translation_key}"
        )

        self._attr_unique_id = f"refresh_rate_{config_entry.entry_id}"
        self._attr_options = UPDATE_RATE_OPTIONS
        self._attr_current_option = str(config_entry.options.get("update_rate", 10))

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        try:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, "update_rate": int(option)},
            )
            self._attr_current_option = option
            self.async_write_ha_state()
            LOGGER.info("select.py → update_rate changed to %s seconds", option)
        except Exception:
            LOGGER.exception("select.py → error writing update_rate=%s", option)

    @property
    def available(self) -> bool:
        """Return true if the select is available."""
        return True

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
