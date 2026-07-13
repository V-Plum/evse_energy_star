import asyncio
import logging
from datetime import timedelta

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_UPDATE_RATE,
    DOMAIN,
    INIT_ALLOWED_KEYS,
    INIT_SECRET_KEYS,
)

_LOGGER = logging.getLogger(__name__)


class EVSECoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, entry: ConfigEntry):
        update_rate = entry.options.get("update_rate", DEFAULT_UPDATE_RATE)
        super().__init__(
            hass,
            _LOGGER,
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

    @property
    def request_timeout(self) -> int:
        return int(self.entry.options.get("request_timeout", DEFAULT_REQUEST_TIMEOUT))

    async def _async_update_data(self):
        # Спільна сесія Home Assistant замість aiohttp.ClientSession() на кожен
        # цикл. При update_rate=1 стара схема створювала ~86 000 сесій на добу,
        # без keep-alive і з постійним переустановленням зʼєднання.
        session = async_get_clientsession(self.hass)

        # /init — допоміжний (часовий пояс, розклад). Якщо він недоступний,
        # це не привід валити весь цикл: телеметрія живе в /main.
        init_data = {}
        try:
            init_data = await self._post_json(session, "/init")
        except Exception as err:  # noqa: BLE001 — навмисно терпимо
            _LOGGER.warning(
                "EVSECoordinator → /init недоступний (%s), продовжуємо лише з /main",
                repr(err),
            )

        # /main — обовʼязковий. Якщо його немає, даних немає, і про це має знати
        # Home Assistant: UpdateFailed переведе сутності в unavailable і ввімкне
        # backoff. Раніше тут повертався порожній {}, тому last_update_success
        # лишався True — сутності виглядали "доступними", але були порожні,
        # і збій станції ніяк себе не проявляв.
        main_data = await self._post_json(session, "/main")
        if not main_data:
            raise UpdateFailed(f"/main повернув порожню відповідь ({self.host})")

        # З /init беремо лише дозволені ключі: у ньому лежать паролі Wi-Fi та
        # HTTP відкритим текстом, і їм не місце ні в coordinator.data, ні в логах.
        safe_init = {k: v for k, v in init_data.items() if k in INIT_ALLOWED_KEYS}

        return {**safe_init, **main_data}

    async def _post_json(self, session: aiohttp.ClientSession, path: str) -> dict:
        """POST з порожнім тілом — рівно так робить веб-інтерфейс станції.

        Раніше в /main летіло json={"getState": True}. Такого параметра станція
        не знає (у її власному JS слова getState немає жодного разу) — вона його
        просто ігнорує. Перевірено: відповіді з порожнім тілом і з getState
        побайтово однакові. Прибрано, щоб не вигадувати протокол.
        """
        url = f"http://{self.host}{path}"
        try:
            async with async_timeout.timeout(self.request_timeout):
                async with session.post(url) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"{path} → HTTP {resp.status} ({self.host})")

                    ctype = resp.headers.get("Content-Type", "")
                    if "application/json" not in ctype:
                        raise UpdateFailed(f"{path} → відповідь не JSON ({ctype})")

                    data = await resp.json()

        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                f"{path} → тайм-аут {self.request_timeout} с ({self.host})"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"{path} → помилка зʼєднання: {err!r} ({self.host})") from err

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "EVSECoordinator → %s: %s",
                path,
                {k: v for k, v in data.items() if k not in INIT_SECRET_KEYS},
            )

        return data
