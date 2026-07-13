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
# ЧОМУ /10, тобто 0.1:
#
# 1. Веб-інтерфейс САМОЇ станції ділить на 10 — це найпряміший доказ, бо це її
#    власний, еталонний клієнт (js/script-min.js):
#        sessionEnergyValue.textContent = (e.sessionEnergy / 10).toFixed(1)
#        totalEnergyValue.textContent   = (e.totalEnergy / 10).toFixed(1)
#        EVSE.curMeas1                  = (e.curMeas1 / 10).toFixed(1)
#        energyLimitValue.textContent   = (EVSE.energyLimit / 10).toFixed(1)
#
# 2. Сирі значення це підтверджують: curMeas1=151 при зарядці 16 А -> 15.1 A.
#    Без ділення вийшло б 151 A, чого фізично не буває.
#
# 3. Здоровий глузд: sessionEnergy=128 -> 12.8 kWh (правдоподібна сесія).
#    Без ділення — 128 kWh, більше за батарею більшості електромобілів.
#
# 4. Сама станція має вбудовану валідацію testValid(), яка відкидає пакет при
#    sessionEnergy > 10000, тобто "стеля" в її ж одиницях = 1000.0 kWh.
#
# ЧОМУ ЦЕ ВСЕ ОДНО ОПЦІЯ, А НЕ КОНСТАНТА:
#
# Тому що прошивки РІЗНІ, і це доведено, а не припущено. Найяскравіший доказ —
# systemTime: наша прошивка віддає його РЯДКОМ "22:36:22", а форк
# d-primikirio/eveus_hacs конвертує це поле з Unix timestamp. Обидва працюють —
# просто на різному залізі. Так само й з масштабом: автори ababak і pirelly
# НЕЗАЛЕЖНО один від одного "виправили" ділення на 10, бо в них воно давало
# значення в 10 разів менші. Вони не помилялись — у них інша станція.
#
# Тому вибирати одну правду для всіх не можна: будь-який вибір зламає половину
# користувачів. Масштаб має бути налаштуванням.
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
