"""Sensor platform for Kano Wand."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_TYPE_RECENTRE, SIGNAL_WAND_SPELL
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand sensors."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandSpellSensor(entry, wand)])


class KanoWandSpellSensor(KanoWandBaseEntity, SensorEntity):
    """Sensor for the last recognized spell."""

    _attr_name = "Last Spell"
    _attr_icon = "mdi:magic-staff"

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_last_spell"
        self._state: str | None = None
        self._attrs: dict[str, Any] = {}

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_SPELL.format(self.entry.entry_id),
                self._update_spell,
            )
        )

    @callback
    def _update_spell(self, spell_data: dict[str, Any]) -> None:
        """Update the spell state."""
        spell = spell_data.get("spell")
        if spell == EVENT_TYPE_RECENTRE:
            return
        self._state = spell
        self._attrs = {
            "score": spell_data.get("score"),
            "duration": spell_data.get("duration"),
            "points": spell_data.get("points"),
        }
        self.async_write_ha_state()

