"""Select platform for Kano Wand vibration pattern selection."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, VIBRATION_PATTERNS
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand select entities."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandVibrationPatternSelect(entry, wand)])


class KanoWandVibrationPatternSelect(KanoWandBaseEntity, SelectEntity, RestoreEntity):
    """Select entity to choose and preview the Kano Wand haptic vibration pattern."""

    _attr_name = "Vibration Pattern"
    _attr_icon = "mdi:waveform"
    _attr_options = list(VIBRATION_PATTERNS.keys())

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the vibration pattern select entity."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_vibration_pattern"
        self._attr_current_option = wand.vibration_pattern

    async def async_added_to_hass(self) -> None:
        """Restore the previously selected vibration pattern on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state
                self.wand.vibration_pattern = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select a vibration pattern and trigger a preview if connected."""
        self._attr_current_option = option
        self.wand.vibration_pattern = option
        self.async_write_ha_state()
        if self.wand.is_connected:
            await self.wand.vibrate(option)
