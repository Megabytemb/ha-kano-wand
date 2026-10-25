"""Constants for the Kano Wand integration."""
from __future__ import annotations

DOMAIN = "kano_wand"

# BLE Service & Characteristic UUIDs (from Kano Wand hardware specification)
SERVICE_INFO = "64A70010-F691-4B93-A6F4-0968F5B648F8"
CHAR_ORGANIZATION = "64A7000B-F691-4B93-A6F4-0968F5B648F8"
CHAR_SOFTWARE = "64A70013-F691-4B93-A6F4-0968F5B648F8"
CHAR_HARDWARE = "64A70001-F691-4B93-A6F4-0968F5B648F8"

SERVICE_IO = "64A70012-F691-4B93-A6F4-0968F5B648F8"
CHAR_BATTERY = "64A70007-F691-4B93-A6F4-0968F5B648F8"
CHAR_BUTTON = "64A7000D-F691-4B93-A6F4-0968F5B648F8"
CHAR_VIBRATOR = "64A70008-F691-4B93-A6F4-0968F5B648F8"
CHAR_LED = "64A70009-F691-4B93-A6F4-0968F5B648F8"
CHAR_KEEP_ALIVE = "64A7000F-F691-4B93-A6F4-0968F5B648F8"

SERVICE_SENSOR = "64A70011-F691-4B93-A6F4-0968F5B648F8"
CHAR_TEMP = "64A70014-F691-4B93-A6F4-0968F5B648F8"
CHAR_QUATERNIONS = "64A70002-F691-4B93-A6F4-0968F5B648F8"
CHAR_RAW = "64A7000A-F691-4B93-A6F4-0968F5B648F8"
CHAR_MOTION = "64A7000C-F691-4B93-A6F4-0968F5B648F8"
CHAR_MAGN_CALIBRATE = "64A70021-F691-4B93-A6F4-0968F5B648F8"
CHAR_QUATERNIONS_RESET = "64A70004-F691-4B93-A6F4-0968F5B648F8"

# Haptic Vibration Patterns
VIBRATION_REGULAR = 1
VIBRATION_SHORT = 2
VIBRATION_BURST = 3
VIBRATION_LONG = 4
VIBRATION_SHORT_LONG = 5
VIBRATION_SHORT_SHORT = 6
VIBRATION_BIG_PAUSE = 7

VIBRATION_PATTERNS: dict[str, int] = {
    "regular": VIBRATION_REGULAR,
    "short": VIBRATION_SHORT,
    "burst": VIBRATION_BURST,
    "long": VIBRATION_LONG,
    "short_long": VIBRATION_SHORT_LONG,
    "short_short": VIBRATION_SHORT_SHORT,
    "big_pause": VIBRATION_BIG_PAUSE,
}

# Spells recognized by the TFLite gesture model
# IMPORTANT: Must remain sorted in ASCII/UTF-16 order matching gesture-spells.js `.sort()`
SPELLS: list[str] = [
    "Accio",
    "Aguamenti",
    "Alohomora",
    "Avis",
    "Bombarda",
    "Colovaria",
    "Engorgio",
    "Epoximise",
    "Evanesco",
    "Expelliarmus",
    "Flipendo",
    "Fumos",
    "Gemino",
    "Impedimenta",
    "Incendio",
    "Locomotor",
    "Lumos",
    "Oppugno",
    "Orchideous",
    "Reducio",
    "Reducto",
    "Reparo",
    "Serpensortia",
    "Vermillious",
    "Wingardium Leviosa",
    "not a Spell",
]

EVENT_TYPE_RECENTRE = "recentre"
SPELL_EVENT_TYPES: list[str] = [*SPELLS, EVENT_TYPE_RECENTRE]
REAL_SPELLS: list[str] = [s for s in SPELLS if s != "not a Spell"]

# Keep-alive timeout configuration (in minutes)
DEFAULT_KEEP_ALIVE_TIMEOUT_MINUTES = 3.0
MIN_KEEP_ALIVE_TIMEOUT_MINUTES = 0.0
MAX_KEEP_ALIVE_TIMEOUT_MINUTES = 30.0
STEP_KEEP_ALIVE_TIMEOUT_MINUTES = 0.5
KEEP_ALIVE_INTERVAL_SECONDS = 10.0

# Dispatcher signals
SIGNAL_WAND_BUTTON = "kano_wand_button_{}"
SIGNAL_WAND_SPELL = "kano_wand_spell_{}"
SIGNAL_WAND_BATTERY = "kano_wand_battery_{}"
SIGNAL_WAND_CONNECTED = "kano_wand_connected_{}"
SIGNAL_WAND_LED = "kano_wand_led_{}"

# Services
SERVICE_VIBRATE = "vibrate"
ATTR_PATTERN = "pattern"
