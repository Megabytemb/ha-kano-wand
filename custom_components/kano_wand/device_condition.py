"""Provides device conditions for Kano Wand."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN
from .device_action import _get_wand_for_device

CONDITION_TYPES: list[str] = [
    "is_connected",
    "is_disconnected",
    "is_button_pressed",
]

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device conditions for Kano Wand devices."""
    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    return [{**base_condition, CONF_TYPE: cond_type} for cond_type in CONDITION_TYPES]


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a Kano Wand device condition."""
    cond_type: str = config[CONF_TYPE]
    device_id: str = config[CONF_DEVICE_ID]

    @callback
    def test_condition(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Evaluate the condition against the active KanoWand instance."""
        wand = _get_wand_for_device(hass, device_id)
        if wand is None:
            return False
        if cond_type == "is_connected":
            return wand.is_connected
        if cond_type == "is_disconnected":
            return not wand.is_connected
        if cond_type == "is_button_pressed":
            return wand.button_pressed
        return False

    return test_condition
