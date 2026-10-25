"""Describe Kano Wand logbook events for the Device Activity feed."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_KANO_WAND_SPELL, EVENT_TYPE_RECENTRE


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Describe logbook events for Kano Wand."""

    @callback
    def async_describe_spell_event(event: Event) -> dict[str, Any]:
        """Describe a kano_wand_spell logbook event."""
        data = event.data
        name = data.get("name") or "Kano Wand"
        spell = data.get("spell")
        score = data.get("score")
        device_id = data.get(ATTR_DEVICE_ID)

        if spell == EVENT_TYPE_RECENTRE:
            message = "recentered its orientation"
        elif score is not None:
            pct = round(float(score) * 100)
            message = f"cast {spell} ({pct}% confidence)"
        else:
            message = f"cast {spell}"

        result: dict[str, Any] = {
            "name": name,
            "message": message,
        }
        if device_id:
            result["device_id"] = device_id
        return result

    async_describe_event(DOMAIN, EVENT_KANO_WAND_SPELL, async_describe_spell_event)
