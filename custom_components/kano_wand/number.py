"""Number platform for dynamically configuring Kano Wand keep-alive timeout."""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_KEEP_ALIVE_TIMEOUT_MINUTES,
    DOMAIN,
    MAX_KEEP_ALIVE_TIMEOUT_MINUTES,
    MIN_KEEP_ALIVE_TIMEOUT_MINUTES,
    STEP_KEEP_ALIVE_TIMEOUT_MINUTES,
)
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand number entities."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandKeepAliveTimeoutNumber(entry, wand)])


class KanoWandKeepAliveTimeoutNumber(KanoWandBaseEntity, RestoreNumber):
    """Slider to configure how long the wand stays awake after activity."""

    _attr_name = "Keep Alive Timeout"
    _attr_icon = "mdi:timer-Sleep-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = MIN_KEEP_ALIVE_TIMEOUT_MINUTES
    _attr_native_max_value = MAX_KEEP_ALIVE_TIMEOUT_MINUTES
    _attr_native_step = STEP_KEEP_ALIVE_TIMEOUT_MINUTES
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the keep-alive timeout slider."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_keep_alive_timeout"
        self._attr_native_value = DEFAULT_KEEP_ALIVE_TIMEOUT_MINUTES

    async def async_added_to_hass(self) -> None:
        """Restore previous timeout setting on Home Assistant startup."""
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_number_data()) is not None:
            if last_data.native_value is not None:
                self._attr_native_value = float(last_data.native_value)
                self.wand.set_keep_alive_timeout(self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the keep-alive timeout dynamically."""
        self._attr_native_value = float(value)
        self.wand.set_keep_alive_timeout(self._attr_native_value)
        self.async_write_ha_state()
