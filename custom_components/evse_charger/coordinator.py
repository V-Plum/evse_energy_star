"""Coordinator for EVSE Charger."""

import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import CONF_DEVICE_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__name__)


class EVSECoordinator(DataUpdateCoordinator):
    """EVSE Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        update_rate = entry.options.get("update_rate", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} Coordinator",
            update_interval=timedelta(seconds=update_rate),
        )
        self.hass = hass
        self.host = host
        self.entry = entry

        self.device_name = entry.options.get(
            CONF_DEVICE_NAME, entry.data.get(CONF_DEVICE_NAME, "Eveus Pro")
        )

        self.device_name_slug = slugify(self.device_name)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    init_url = f"http://{self.host}/init"
                    LOGGER.debug("EVSECoordinator → POST /init: %s", init_url)

                    init_data = {}
                    try:
                        async with session.post(init_url) as resp_init:
                            if (
                                resp_init.status == 200
                                and "application/json"
                                in resp_init.headers.get("Content-Type", "")
                            ):
                                init_data = await resp_init.json()
                                LOGGER.debug("EVSECoordinator → Data from /init:")
                                for key, value in init_data.items():
                                    LOGGER.debug(
                                        "  %s → %s (%s)",
                                        key,
                                        value,
                                        type(value).__name__,
                                    )
                            else:
                                LOGGER.warning(
                                    "EVSECoordinator → /init → not JSON (%s)",
                                    resp_init.headers.get("Content-Type"),
                                )
                    except Exception:
                        LOGGER.exception("EVSECoordinator → error requesting /init")

                    main_url = f"http://{self.host}/main"
                    LOGGER.debug("EVSECoordinator → POST /main: %s", main_url)

                    main_data = {}
                    try:
                        async with session.post(
                            main_url, json={"getState": True}
                        ) as resp_main:
                            if (
                                resp_main.status == 200
                                and "application/json"
                                in resp_main.headers.get("Content-Type", "")
                            ):
                                main_data = await resp_main.json()
                                LOGGER.debug("EVSECoordinator → Data from /main:")
                                for key, value in main_data.items():
                                    LOGGER.debug(
                                        "  %s → %s (%s)",
                                        key,
                                        value,
                                        type(value).__name__,
                                    )
                            else:
                                LOGGER.warning(
                                    "EVSECoordinator → /main → not JSON (%s)",
                                    resp_main.headers.get("Content-Type"),
                                )
                    except Exception:
                        LOGGER.exception("EVSECoordinator → error requesting /main")

                    return {**init_data, **main_data}

        except Exception:
            LOGGER.exception("EVSECoordinator → general error")
            return {}
