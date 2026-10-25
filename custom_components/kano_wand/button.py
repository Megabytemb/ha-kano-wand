"""Button platform for triggering Kano Wand haptic vibration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VIBRATION_REGULAR
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand button entities."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandVibrateButton(entry, wand)])


class KanoWandVibrateButton(KanoWandBaseEntity, ButtonEntity):
    """Button entity to vibrate the Kano Wand."""

    _attr_name = "Vibrate"
    _attr_icon = "mdi:vibrate"

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the vibrate button."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_vibrate"

    async def async_press(self) -> None:
        """Trigger a regular vibration on the wand."""
        await self.wand.vibrate(VIBRATION_REGULAR)
