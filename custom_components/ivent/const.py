"""Constants for the i-Vent Cloud integration."""

from datetime import timedelta
from enum import StrEnum
from typing import Final

DOMAIN: Final = "ivent"
MANUFACTURER: Final = "i-Vent"
BASE_URL: Final = "https://cloud.i-vent.com/api/v1"

CONF_LOC_ID: Final = "loc_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
MIN_SCAN_INTERVAL_SECONDS: Final = 10
MAX_SCAN_INTERVAL_SECONDS: Final = 300
REQUEST_TIMEOUT_SECONDS: Final = 30


class WorkMode(StrEnum):
    """IVentWorkMode enum from the API."""

    OFF = "IVentWorkOff"
    ON = "IVentOn"
    CUSTOM = "IVentCustom"
    RECUPERATION_1 = "IVentRecuperation1"
    RECUPERATION_2 = "IVentRecuperation2"
    RECUPERATION_3 = "IVentRecuperation3"
    BYPASS_1 = "IVentBypass1"
    BYPASS_2 = "IVentBypass2"
    BYPASS_3 = "IVentBypass3"


class SpecialMode(StrEnum):
    """IVentSpecialMode enum from the API."""

    OFF = "IVentSpecialOff"
    BOOST = "IVentBoost"
    SNOOZE = "IVentSnooze"
    NIGHT_1 = "IVentNight1"
    NIGHT_2 = "IVentNight2"


class BypassRotation(StrEnum):
    """BypassRotation enum from the API."""

    FORWARD = "BypassForward"
    REVERSE = "BypassReverse"


class RemoteControlMode(StrEnum):
    """RemoteControlWorkMode enum from the API."""

    NORMAL = "Normal"
    BYPASS = "Bypass"


class LedMode(StrEnum):
    """LedWorkMode enum from the API."""

    OFF = "LedOffMode"
    ON = "LedOnMode"
    DEBUG = "LedDebugMode"
    OFF_WITH_ERR = "LedOffWithErrMode"


class BuzzerMode(StrEnum):
    """BuzzerWorkMode enum from the API."""

    OFF = "BuzzerOffMode"
    ON = "BuzzerOnMode"
    DEBUG = "BuzzerDebugMode"
    OFF_WITH_ERR = "BuzzerOffWithErrMode"
    ON_MUTE_ERR = "BuzzerOnMuteErrMode"


# Friendly option -> API value maps used by select entities.
FAN_PRESETS: Final[dict[str, WorkMode]] = {
    "On": WorkMode.ON,
    "Custom": WorkMode.CUSTOM,
    "Recuperation 1": WorkMode.RECUPERATION_1,
    "Recuperation 2": WorkMode.RECUPERATION_2,
    "Recuperation 3": WorkMode.RECUPERATION_3,
    "Bypass 1": WorkMode.BYPASS_1,
    "Bypass 2": WorkMode.BYPASS_2,
    "Bypass 3": WorkMode.BYPASS_3,
}
# API value -> friendly option. StrEnum members hash like their string value,
# so plain API strings can be used as lookup keys.
PRESET_TO_WORK_MODE: Final[dict[str, str]] = {mode.value: preset for preset, mode in FAN_PRESETS.items()}

WORK_MODE_OPTIONS: Final[dict[str, WorkMode]] = {"Off": WorkMode.OFF, **FAN_PRESETS}

SPECIAL_MODE_OPTIONS: Final[dict[str, SpecialMode]] = {
    "Off": SpecialMode.OFF,
    "Boost": SpecialMode.BOOST,
    "Snooze": SpecialMode.SNOOZE,
    "Night 1": SpecialMode.NIGHT_1,
    "Night 2": SpecialMode.NIGHT_2,
}

BYPASS_ROTATION_OPTIONS: Final[dict[str, BypassRotation]] = {
    "Forward": BypassRotation.FORWARD,
    "Reverse": BypassRotation.REVERSE,
}

REMOTE_CONTROL_MODE_OPTIONS: Final[dict[str, RemoteControlMode]] = {
    "Normal": RemoteControlMode.NORMAL,
    "Bypass": RemoteControlMode.BYPASS,
}

LED_MODE_OPTIONS: Final[dict[str, LedMode]] = {
    "Off": LedMode.OFF,
    "On": LedMode.ON,
    "Debug": LedMode.DEBUG,
    "Off with errors": LedMode.OFF_WITH_ERR,
}

BUZZER_MODE_OPTIONS: Final[dict[str, BuzzerMode]] = {
    "Off": BuzzerMode.OFF,
    "On": BuzzerMode.ON,
    "Debug": BuzzerMode.DEBUG,
    "Off with errors": BuzzerMode.OFF_WITH_ERR,
    "On, mute errors": BuzzerMode.ON_MUTE_ERR,
}

# remote_control_speed (1-3) <-> HA fan percentage (1-100).
MAX_SPEED: Final = 3
SPEED_TO_PERCENTAGE: Final[dict[int, int]] = {1: 33, 2: 67, 3: 100}


def percentage_to_speed(percentage: int) -> int:
    """Convert a HA fan percentage (1-100) to an API speed (1-3)."""
    return max(1, min(MAX_SPEED, round(percentage * MAX_SPEED / 100)))


# Schedule repeat days bitmask (bit 0 = Monday ... bit 6 = Sunday) presets.
CUSTOM_DAYS: Final = "Custom"
DAY_PRESETS: Final[dict[str, int]] = {
    "Every day": 0b1111111,
    "Weekdays": 0b0011111,
    "Weekends": 0b1100000,
    "Monday": 0b0000001,
    "Tuesday": 0b0000010,
    "Wednesday": 0b0000100,
    "Thursday": 0b0001000,
    "Friday": 0b0010000,
    "Saturday": 0b0100000,
    "Sunday": 0b1000000,
}
