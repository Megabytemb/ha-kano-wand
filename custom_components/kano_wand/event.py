"""Event platform for Kano Wand spells and gestures."""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLICK_DIRECTIONS,
    SIGNAL_WAND_FLICK,
    SIGNAL_WAND_SPELL,
    SPELL_EVENT_TYPES,
)
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand event entities."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            KanoWandSpellEvent(entry, wand),
            KanoWandFlickEvent(entry, wand),
        ]
    )


class KanoWandSpellEvent(KanoWandBaseEntity, EventEntity):
    """Event entity triggered whenever a spell is cast or wand is recentred."""

    _attr_name = "Spell"
    _attr_icon = "mdi:auto-fix"
    _attr_event_types = SPELL_EVENT_TYPES

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the spell event entity."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_spell_event"

    async def async_added_to_hass(self) -> None:
        """Subscribe to spell dispatcher signals."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_SPELL.format(self.entry.entry_id),
                self._async_handle_spell,
            )
        )

    @callback
    def _async_handle_spell(self, spell_data: dict[str, Any]) -> None:
        """Trigger the HA event entity when a spell is recognized."""
        spell_name = spell_data.get("spell")
        if not spell_name or spell_name not in self.event_types:
            return
        self._trigger_event(
            spell_name,
            {
                "score": spell_data.get("score"),
                "duration": spell_data.get("duration"),
                "points": spell_data.get("points"),
            },
        )
        self.async_write_ha_state()


class KanoWandFlickEvent(KanoWandBaseEntity, EventEntity):
    """Event entity triggered on directional wand flicks (up, down, left, right)."""

    _attr_name = "Flick"
    _attr_icon = "mdi:gesture-swipe"
    _attr_event_types = FLICK_DIRECTIONS

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the flick event entity."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_flick_event"

    async def async_added_to_hass(self) -> None:
        """Subscribe to flick dispatcher signals."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_FLICK.format(self.entry.entry_id),
                self._async_handle_flick,
            )
        )

    @callback
    def _async_handle_flick(self, flick_data: dict[str, Any]) -> None:
        """Trigger the HA event entity when a directional flick is detected."""
        direction = flick_data.get("direction")
        if not direction or direction not in self.event_types:
            return
        self._trigger_event(
            direction,
            {
                "direction": direction,
                "intensity": flick_data.get("intensity"),
            },
        )
        self.async_write_ha_state()
