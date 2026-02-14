"""EVSE Charger integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    DOMAIN,
)
from .coordinator import EVSECoordinator
from .data import EvseEnergyStarData

LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "select", "button", "number", "switch", "time"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvseEnergyStarData,
) -> bool:
    """Define setup entry."""
    host = entry.options.get(CONF_HOST, entry.data.get(CONF_HOST))
    coordinator = EVSECoordinator(hass, host, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        CONF_HOST: host,
        "device_name_slug": coordinator.device_name_slug,
    }

    LOGGER.info(
        "__init__.py → Створено coordinator для %s (%s), частота оновлення: %s сек",
        coordinator.device_name,
        host,
        entry.options.get("update_rate", 10),
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload EVSE config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload EVSE config entry when options are updated."""
    LOGGER.debug("update_listener → перезавантаження інтеграції через зміну опцій")
    await hass.config_entries.async_reload(entry.entry_id)
