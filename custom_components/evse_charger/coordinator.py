"""Coordinator for EVSE Charger."""

import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
        init_data: dict[str, Any] = {}
        main_data: dict[str, Any] = {}
        errors: list[str] = []

        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    init_url = f"http://{self.host}/init"
                    LOGGER.debug("EVSECoordinator → POST /init: %s", init_url)
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
                                msg = (
                                    "/init invalid response: "
                                    f"status={resp_init.status}, "
                                    f"content_type={resp_init.headers.get('Content-Type')}"
                                )
                                errors.append(msg)
                                LOGGER.warning("EVSECoordinator → %s", msg)
                    except Exception as err:
                        msg = f"/init request error: {err}"
                        errors.append(msg)
                        LOGGER.exception("EVSECoordinator → error requesting /init")

                    main_url = f"http://{self.host}/main"
                    LOGGER.debug("EVSECoordinator → POST /main: %s", main_url)
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
                                msg = (
                                    "/main invalid response: "
                                    f"status={resp_main.status}, "
                                    f"content_type={resp_main.headers.get('Content-Type')}"
                                )
                                errors.append(msg)
                                LOGGER.warning("EVSECoordinator → %s", msg)
                    except Exception as err:
                        msg = f"/main request error: {err}"
                        errors.append(msg)
                        LOGGER.exception("EVSECoordinator → error requesting /main")

        except Exception as err:
            error_message = f"Coordinator update failed: {err}"
            raise UpdateFailed(error_message) from err

        data = {**init_data, **main_data}
        if not data:
            error_message = "Coordinator update failed: no data returned. " + (
                "; ".join(errors) if errors else "no additional error details"
            )
            raise UpdateFailed(error_message)

        return data
