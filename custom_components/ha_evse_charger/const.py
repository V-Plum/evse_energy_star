DOMAIN: Final = "ha_evse_charger"
DEFAULT_SCAN_INTERVAL = 30
TITLE = "EVSE Energy Star"

STATUS_MAP: Final = {
    0: 'power_up',
    1: 'self_test',
    2: 'standby',
    3: 'car_connected',
    4: 'charging',
    5: 'charging_complete',
    6: 'disabled',
    7: 'error'

    # 0: "no_data",
    # 6: "charging",
    # 9: "waiting",
    # 12: "ready",
    # 13: "delayed_start",
    # 14: "overcurrent",
    # 15: "overvoltage",
    # 16: "leakage",
    # 17: "station_error",
    # 18: "overtemperature",
    # 19: "locked",
    # 20: "no_ground",
    # 21: "plug_overheat",
    # 22: "undervoltage",
}

# Configuration option
CONF_HOST: Final = "host"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_UPDATE_RATE: Final = "update_rate"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

DEVICE_TYPES: Final = ["1_phase", "3_phase"]
