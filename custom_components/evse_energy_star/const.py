DOMAIN = "evse_energy_star"
DEFAULT_SCAN_INTERVAL = 30
TITLE = "EVSE Energy Star"

# Частота опитування (керується select-ом "update_rate")
DEFAULT_UPDATE_RATE = 10

# Тайм-аут HTTP-запиту до станції. Раніше було жорстко 5 с — цього замало для
# станції, яка "задумалась": запит падав, і ВСІ сутності разом провалювались
# в unavailable і назад.
DEFAULT_REQUEST_TIMEOUT = 15

# Масштаб телеметрії струму та енергії.
#
# Прошивка віддає струм і енергію в ДЕСЯТИХ (curMeas1=160 -> 16.0 A,
# sessionEnergy=128 -> 12.8 kWh). Це підтверджено власним веб-інтерфейсом
# станції, який робить рівно те саме:
#     sessionEnergyValue.textContent = (e.sessionEnergy / 10).toFixed(1)
#     EVSE.curMeas1                  = (e.curMeas1 / 10).toFixed(1)
#
# Але користувачі з іншою прошивкою (issue #7) бачили значення в 10 разів
# менші — їхня станція, схоже, віддає вже готові одиниці. Тому масштаб
# винесено в опцію замість того, щоб ділити або не ділити для всіх одразу.
#
# Напруга і температури НЕ масштабуються — вони сирі в обох прошивках.
DEFAULT_VALUE_SCALE = 0.1
VALUE_SCALE_OPTIONS = {
    0.1: "0.1 — станція віддає десяті (типово)",
    1.0: "1.0 — станція віддає готові одиниці",
}

# --- /init ---
#
# УВАГА: POST /init повертає ssidPassword, httpPassword та httpUsername
# ВІДКРИТИМ ТЕКСТОМ. Раніше координатор (а) зливав увесь словник у
# coordinator.data, звідки його бачила будь-яка сутність, і (б) логував КОЖЕН
# ключ на рівні DEBUG — тобто пароль від Wi-Fi потрапляв у home-assistant.log,
# який користувачі прикладають до баг-репортів.
#
# Тепер з /init беремо лише те, що реально потрібне інтеграції...
INIT_ALLOWED_KEYS = {"timeZone", "startTime", "stopTime", "isAlarm"}

# ...а це не потрапляє ні в дані, ні в лог.
INIT_SECRET_KEYS = {
    "ssidPassword",
    "ssidPasswordAP",
    "httpPassword",
    "httpUsername",
}

# Повертаємо КЛЮЧІ, а не тексти
STATUS_MAP = {
    0: "no_data",
    6: "charging",
    9: "waiting",
    12: "ready",
    13: "delayed_start",
    14: "overcurrent",
    15: "overvoltage",
    16: "leakage",
    17: "station_error",
    18: "overtemperature",
    19: "locked",
    20: "no_ground",
    21: "plug_overheat",
    22: "undervoltage",
}
