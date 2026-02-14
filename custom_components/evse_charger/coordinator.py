import logging
import aiohttp
import async_timeout
from datetime import timedelta
from homeassistant.util import slugify
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

class EVSECoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, entry: ConfigEntry):
        update_rate = entry.options.get("update_rate", 10)
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} Coordinator",
            update_interval=timedelta(seconds=update_rate),
        )
        self.hass = hass
        self.host = host
        self.entry = entry

        # Зберігаємо назву пристрою
        self.device_name = entry.options.get(
            "device_name",
            entry.data.get("device_name", "Eveus Pro")
        )

        # Одразу зберігаємо slug, щоб уникнути дублювання коду в сутностях
        self.device_name_slug = slugify(self.device_name)

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:

                    # 🟡 КРОК 1: POST /init
                    init_url = f"http://{self.host}/init"
                    LOGGER.debug("EVSECoordinator → POST /init: %s", init_url)

                    init_data = {}
                    try:
                        async with session.post(init_url) as resp_init:
                            if resp_init.status == 200 and "application/json" in resp_init.headers.get("Content-Type", ""):
                                init_data = await resp_init.json()
                                LOGGER.debug("EVSECoordinator → Дані з /init:")
                                for key, value in init_data.items():
                                    LOGGER.debug("  %s → %s (%s)", key, value, type(value).__name__)
                            else:
                                LOGGER.warning("EVSECoordinator → /init → не JSON (%s)", resp_init.headers.get("Content-Type"))
                    except Exception as err:
                        LOGGER.error("EVSECoordinator → помилка запиту /init: %s", repr(err))

                    # 🟢 КРОК 2: POST /main
                    main_url = f"http://{self.host}/main"
                    LOGGER.debug("EVSECoordinator → POST /main: %s", main_url)

                    main_data = {}
                    try:
                        async with session.post(main_url, json={"getState": True}) as resp_main:
                            if resp_main.status == 200 and "application/json" in resp_main.headers.get("Content-Type", ""):
                                main_data = await resp_main.json()
                                LOGGER.debug("EVSECoordinator → Дані з /main:")
                                for key, value in main_data.items():
                                    LOGGER.debug("  %s → %s (%s)", key, value, type(value).__name__)
                            else:
                                LOGGER.warning("EVSECoordinator → /main → не JSON (%s)", resp_main.headers.get("Content-Type"))
                    except Exception as err:
                        LOGGER.error("EVSECoordinator → помилка запиту /main: %s", repr(err))

                    # 🔗 Обʼєднання даних
                    combined = {**init_data, **main_data}
                    return combined

        except Exception as err:
            LOGGER.error("EVSECoordinator → загальна помилка: %s", repr(err))
            return {}
