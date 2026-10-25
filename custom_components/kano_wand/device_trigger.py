"""Provides device triggers for Kano Wand via internal dispatcher signals."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    EVENT_TYPE_RECENTRE,
    REAL_SPELLS,
    SIGNAL_WAND_BUTTON,
    SIGNAL_WAND_CONNECTED,
    SIGNAL_WAND_SPELL,
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


def _get_entry_ids_for_device(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return config entry IDs belonging to the given Home Assistant device_id."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get(device_id):
        return list(device.config_entries)
    return list(hass.data.get(DOMAIN, {}).keys())


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
    """Attach a Kano Wand device trigger using internal dispatcher signals."""
    trigger_type: str = config[CONF_TYPE]
    subtype: str | None = config.get(CONF_SUBTYPE)
    device_id: str = config[CONF_DEVICE_ID]
    trigger_data: dict[str, Any] = (
        trigger_info.get("trigger_data", {}) if trigger_info else {}
    )
    job = HassJob(action)
    entry_ids = _get_entry_ids_for_device(hass, device_id)
    unsubs: list[CALLBACK_TYPE] = []

    base_payload: dict[str, Any] = {
        **trigger_data,
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device_id,
        "type": trigger_type,
        "subtype": subtype,
    }

    if trigger_type in (
        TRIGGER_TYPE_SPELL_CAST,
        TRIGGER_TYPE_ANY_SPELL,
        TRIGGER_TYPE_RECENTRE,
    ):

        @callback
        def _handle_spell(spell_data: dict[str, Any]) -> None:
            spell = spell_data.get("spell")
            if trigger_type == TRIGGER_TYPE_SPELL_CAST and spell != subtype:
                return
            if trigger_type == TRIGGER_TYPE_ANY_SPELL and (
                not spell or spell == EVENT_TYPE_RECENTRE
            ):
                return
            if trigger_type == TRIGGER_TYPE_RECENTRE and spell != EVENT_TYPE_RECENTRE:
                return

            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **base_payload,
                        "spell": spell,
                        "score": spell_data.get("score"),
                        "duration": spell_data.get("duration"),
                        "points": spell_data.get("points"),
                        "description": f"Kano Wand spell: {spell}",
                    }
                },
            )

        for entry_id in entry_ids:
            unsubs.append(
                async_dispatcher_connect(
                    hass, SIGNAL_WAND_SPELL.format(entry_id), _handle_spell
                )
            )

    elif trigger_type in (TRIGGER_TYPE_BUTTON_PRESSED, TRIGGER_TYPE_BUTTON_RELEASED):
        expected_pressed = trigger_type == TRIGGER_TYPE_BUTTON_PRESSED

        @callback
        def _handle_button(pressed: bool) -> None:
            if pressed == expected_pressed:
                hass.async_run_hass_job(
                    job,
                    {
                        "trigger": {
                            **base_payload,
                            "description": f"Kano Wand {trigger_type}",
                        }
                    },
                )

        for entry_id in entry_ids:
            unsubs.append(
                async_dispatcher_connect(
                    hass, SIGNAL_WAND_BUTTON.format(entry_id), _handle_button
                )
            )

    elif trigger_type in (TRIGGER_TYPE_CONNECTED, TRIGGER_TYPE_DISCONNECTED):
        expected_connected = trigger_type == TRIGGER_TYPE_CONNECTED

        @callback
        def _handle_connected(connected: bool) -> None:
            if connected == expected_connected:
                hass.async_run_hass_job(
                    job,
                    {
                        "trigger": {
                            **base_payload,
                            "description": f"Kano Wand {trigger_type}",
                        }
                    },
                )

        for entry_id in entry_ids:
            unsubs.append(
                async_dispatcher_connect(
                    hass, SIGNAL_WAND_CONNECTED.format(entry_id), _handle_connected
                )
            )

    @callback
    def _async_remove() -> None:
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    return _async_remove
