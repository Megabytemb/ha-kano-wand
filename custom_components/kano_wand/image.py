"""Image platform for visualizing the last drawn Kano Wand spell trajectory."""
from __future__ import annotations

from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_TYPE_RECENTRE, SIGNAL_WAND_SPELL
from .drawing import render_spell_png
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kano Wand spell drawing image entity."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandSpellImage(hass, entry, wand)])


class KanoWandSpellImage(KanoWandBaseEntity, ImageEntity):
    """Image entity displaying the last drawn wand motion path."""

    _attr_name = "Last Spell Drawing"
    _attr_icon = "mdi:gesture"
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, wand: KanoWand
    ) -> None:
        """Initialize the image entity."""
        KanoWandBaseEntity.__init__(self, entry, wand)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{entry.entry_id}_last_spell_drawing"
        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_png: bytes = render_spell_png(None)
        self._last_spell_data: dict[str, Any] = {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata about the rendered spell path."""
        if not self._last_spell_data:
            return {}
        return {
            "spell": self._last_spell_data.get("spell"),
            "score": self._last_spell_data.get("score"),
            "duration": self._last_spell_data.get("duration"),
            "points": self._last_spell_data.get("points"),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to spell dispatcher updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_SPELL.format(self.entry.entry_id),
                self._async_on_spell,
            )
        )

    @callback
    def _async_on_spell(self, spell_data: dict[str, Any]) -> None:
        """Render a new PNG when a spell motion is completed."""
        if spell_data.get("spell") == EVENT_TYPE_RECENTRE:
            return
        self._last_spell_data = spell_data
        self._cached_png = render_spell_png(spell_data)
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._cached_png
