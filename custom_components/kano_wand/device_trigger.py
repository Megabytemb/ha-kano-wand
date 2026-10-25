"""Provides device triggers for Kano Wand."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    EVENT_KANO_WAND_SPELL,
    EVENT_KANO_WAND_STATUS,
    EVENT_TYPE_RECENTRE,
    REAL_SPELLS,
)

CONF_SUBTYPE = "subtype"

TRIGGER_TYPE_SPELL_CAST = "spell_cast"
TRIGGER_TYPE_ANY_SPELL = "any_spell"
TRIGGER_TYPE_RECENTRE = "recentre"
TRIGGER_TYPE_BUTTON_PRESSED = "button_pressed"
TRIGGER_TYPE_BUTTON_RELEASED = "button_released"
TRIGGER_TYPE_CONNECTED = "connected"
TRIGGER_TYPE_DISCONNECTED = "disconnected"

SIMPLE_TRIGGER_TYPES: list[str] = [
    TRIGGER_TYPE_ANY_SPELL,
    TRIGGER_TYPE_RECENTRE,
    TRIGGER_TYPE_BUTTON_PRESSED,
    TRIGGER_TYPE_BUTTON_RELEASED,
    TRIGGER_TYPE_CONNECTED,
    TRIGGER_TYPE_DISCONNECTED,
]

STATUS_TRIGGER_TYPES: set[str] = {
    TRIGGER_TYPE_BUTTON_PRESSED,
    TRIGGER_TYPE_BUTTON_RELEASED,
    TRIGGER_TYPE_CONNECTED,
    TRIGGER_TYPE_DISCONNECTED,
}

TRIGGER_SCHEMA = vol.Any(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): TRIGGER_TYPE_SPELL_CAST,
            vol.Required(CONF_SUBTYPE): vol.In(REAL_SPELLS),
        }
    ),
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): vol.In(SIMPLE_TRIGGER_TYPES),
        }
    ),
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Kano Wand devices."""
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    triggers: list[dict[str, Any]] = [
        {**base_trigger, CONF_TYPE: trigger_type}
        for trigger_type in SIMPLE_TRIGGER_TYPES
    ]
    for spell in REAL_SPELLS:
        triggers.append(
            {
                **base_trigger,
                CONF_TYPE: TRIGGER_TYPE_SPELL_CAST,
                CONF_SUBTYPE: spell,
            }
        )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a Kano Wand device trigger."""
    trigger_type: str = config[CONF_TYPE]
    device_id: str = config[CONF_DEVICE_ID]

    if trigger_type == TRIGGER_TYPE_SPELL_CAST:
        event_type = EVENT_KANO_WAND_SPELL
        event_data: dict[str, Any] = {
            ATTR_DEVICE_ID: device_id,
            "spell": config[CONF_SUBTYPE],
        }
    elif trigger_type == TRIGGER_TYPE_ANY_SPELL:
        event_type = EVENT_KANO_WAND_SPELL
        event_data = {
            ATTR_DEVICE_ID: device_id,
            "is_spell": True,
        }
    elif trigger_type == TRIGGER_TYPE_RECENTRE:
        event_type = EVENT_KANO_WAND_SPELL
        event_data = {
            ATTR_DEVICE_ID: device_id,
            "spell": EVENT_TYPE_RECENTRE,
        }
    else:
        event_type = EVENT_KANO_WAND_STATUS
        event_data = {
            ATTR_DEVICE_ID: device_id,
            "type": trigger_type,
        }

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: event_type,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )
    return await event_trigger.async_attach_trigger(
        hass,
        event_config,
        action,
        trigger_info,
        platform_type="device",
    )
