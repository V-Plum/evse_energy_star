import asyncio
import logging
from datetime import timedelta
from time import monotonic
from typing import Any

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
    PENDING_WRITE_TTL,
    RESTRICTED_MODE_LIMIT,
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

        # Режим обмеження струму (16 А). У СТАНЦІЇ ТАКОГО ПОЛЯ НЕМАЄ — у відповіді
        # /main його немає взагалі, і на станцію воно ніколи не надсилається:
        # летить лише currentSet. Це поняття існує тільки на боці клієнта, і
        # рідний веб-інтерфейс тримає його як звичайну змінну сторінки.
        #
        # None = ще не ініціалізовано (аналог needInit у веб-інтерфейсі).
        self._restricted_mode: bool | None = None

        # Щойно надіслані команди: {ключ: (значення, час_протухання)}.
        # Станція застосовує команду НЕ миттєво — наступні 1-2 відповіді /main
        # ще містять старе значення. Рідний веб-інтерфейс тому просто ігнорує
        # дві наступні відповіді (ignoreCount = 2 у його postPageEvent).
        self._pending: dict[str, tuple[Any, float]] = {}

    @property
    def request_timeout(self) -> int:
        return int(self.entry.options.get("request_timeout", DEFAULT_REQUEST_TIMEOUT))

    # ------------------------------------------------------------------
    # Щойно надіслані команди (аналог ignoreCount у веб-інтерфейсі станції)
    # ------------------------------------------------------------------

    @property
    def pending_ttl(self) -> float:
        """Скільки довіряти щойно надісланій команді, поки станція не підтвердила.

        МАЄ масштабуватись від update_rate, а не бути константою.

        Станція застосовує команду із затримкою, тому підтвердження приходить не
        раніше ніж через одне-два опитування. При update_rate = 30 с фіксовані
        5 секунд протухали б задовго до наступного опитування — і перемикач
        вискакував би назад, висячи неправильним до півхвилини. Рівно та проблема,
        яку ми лагодили; просто вилазила б при повільному опитуванні.
        """
        rate = (
            self.update_interval.total_seconds()
            if self.update_interval
            else DEFAULT_UPDATE_RATE
        )
        return max(PENDING_WRITE_TTL, rate * 2 + 2)

    def note_write(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Запамʼятати намір: ми щойно надіслали key=value.

        Поки станція не підтвердить (або поки не вийде ttl), сутності показують
        надіслане значення, а не застаріле з /main. Без цього перемикачі
        "вискакують назад": ви натиснули, а наступне опитування повернуло старе
        значення.
        """
        self._pending[key] = (value, monotonic() + (ttl or self.pending_ttl))

    def effective(self, key: str, default: Any = None) -> Any:
        """Значення з урахуванням щойно надісланих команд."""
        return self._effective_from(self.data or {}, key, default)

    def _effective_from(self, data: dict, key: str, default: Any = None) -> Any:
        pending = self._pending.get(key)
        if pending is not None:
            value, expires_at = pending
            if monotonic() >= expires_at:
                # Станція так і не підтвердила — здаємось і віримо їй.
                self._pending.pop(key, None)
            else:
                device_value = data.get(key)
                if device_value is not None and str(device_value) == str(value):
                    # Станція підтвердила — намір більше не потрібен.
                    self._pending.pop(key, None)
                else:
                    return value
        return data.get(key, default)

    # ------------------------------------------------------------------
    # Режим обмеження струму (16 А)
    # ------------------------------------------------------------------

    @property
    def restricted_mode(self) -> bool:
        # До першого успішного опитування вважаємо режим увімкненим: це
        # безпечніший бік (стеля 16 А, а не 32 А).
        return True if self._restricted_mode is None else self._restricted_mode

    def set_restricted_mode(self, value: bool) -> None:
        self._restricted_mode = value

    def _sync_restricted_mode(self, data: dict) -> None:
        """Звірити режим зі станцією РІВНО так, як це робить її веб-інтерфейс.

        Веб-інтерфейс (js/script-min.js) має дві різні поведінки:

        1) При першому завантаженні (needInit) — виводить режим зі струму:
               e.currentSet > 16 ? restrictedMode = false : restrictedMode = true

        2) При кожному наступному оновленні:
               e.currentSet > 16
                 ? (restrictedMode = false, max = curDesign)   // струм підняли -> режим знято
                 : (rangeSliderCurrent.value = e.currentSet)   // <= 16 -> НЕ ЧІПАЄМО режим

        Друге правило — ключове, і саме його бракувало інтеграції. Вона
        перевиводила режим зі струму на КОЖНОМУ оновленні, і виходило замкнене
        коло: вимкнув режим -> струм став 16 -> "16 <= 16, отже режим увімкнено"
        -> стеля назад на 16 -> підняти повзунок вище 16 неможливо взагалі.
        """
        current_set = self._effective_from(data, "currentSet")
        if current_set is None:
            return

        try:
            current = float(current_set)
        except (TypeError, ValueError):
            return

        if self._restricted_mode is None:
            # needInit
            self._restricted_mode = current <= RESTRICTED_MODE_LIMIT
        elif current > RESTRICTED_MODE_LIMIT:
            # Струм підняли вище 16 (з HA, зі станції або з її веб-інтерфейсу)
            # -> режим обмеження знято.
            self._restricted_mode = False
        # current <= 16 -> НЕ ЧІПАЄМО режим. Так робить веб-інтерфейс.

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
        data = {**safe_init, **main_data}

        # Звіряємо режим обмеження струму так само, як це робить веб-інтерфейс
        # станції. Робимо це ДО того, як data потрапить у сутності.
        self._sync_restricted_mode(data)

        return data

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
