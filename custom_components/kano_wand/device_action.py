"""Provides device actions for Kano Wand."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN, VIBRATION_PATTERNS
from .wand import KanoWand

ACTION_TYPES: list[str] = [
    *(f"vibrate_{pattern}" for pattern in VIBRATION_PATTERNS),
    "led_turn_on",
    "led_turn_off",
    "recentre",
    "calibrate_magnetometer",
    "disconnect",
]

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
    }
)


def _get_wand_for_device(hass: HomeAssistant, device_id: str) -> KanoWand | None:
    """Resolve the KanoWand instance associated with a Home Assistant device_id."""
    wands_by_entry: dict[str, KanoWand] = hass.data.get(DOMAIN, {})
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for entry_id in device.config_entries:
            if entry_id in wands_by_entry:
                return wands_by_entry[entry_id]
    return None


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device actions for Kano Wand devices."""
    base_action = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    return [{**base_action, CONF_TYPE: action_type} for action_type in ACTION_TYPES]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a Kano Wand device action."""
    wand = _get_wand_for_device(hass, config[CONF_DEVICE_ID])
    if wand is None:
        return

    action_type: str = config[CONF_TYPE]
    if action_type.startswith("vibrate_"):
        pattern = action_type.removeprefix("vibrate_")
        await wand.vibrate(pattern)
    elif action_type == "led_turn_on":
        await wand.set_led(True)
    elif action_type == "led_turn_off":
        await wand.set_led(False)
    elif action_type == "recentre":
        await wand.reset_position()
    elif action_type == "calibrate_magnetometer":
        await wand.calibrate_magnetometer()
    elif action_type == "disconnect":
        await wand.disconnect()
