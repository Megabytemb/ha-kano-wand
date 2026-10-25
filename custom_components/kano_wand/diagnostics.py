"""Diagnostics support for Kano Wand."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .wand import KanoWand


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    return {
        "name": wand.name,
        "is_connected": wand.is_connected,
        "auto_connect": wand.auto_connect,
        "hardware_version": wand.hardware_version,
        "software_version": wand.software_version,
        "organization": wand.organization,
        "keep_alive_timeout_minutes": wand.keep_alive_timeout_minutes,
        "min_spell_confidence": wand.min_spell_confidence,
        "vibration_pattern": wand.vibration_pattern,
        "vibrate_on_connect": wand.vibrate_on_connect,
        "vibrate_on_spell": wand.vibrate_on_spell,
        "led_on": wand.led_on,
        "led_rgb": list(wand.led_rgb),
        "button_pressed": wand.button_pressed,
        "quaternion_packets_received": wand.quaternion_packets_received,
        "quaternion_rate_hz": wand.quaternion_rate_hz,
    }
