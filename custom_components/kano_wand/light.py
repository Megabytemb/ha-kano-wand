"""Light platform for the Kano Wand RGB tip LED."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_WAND_CONNECTED, SIGNAL_WAND_LED
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kano Wand RGB LED light."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandLedLight(entry, wand)])


class KanoWandLedLight(KanoWandBaseEntity, LightEntity):
    """Representation of the Kano Wand onboard RGB LED."""

    _attr_name = "LED"
    _attr_icon = "mdi:led-on"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the light entity."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_led"
        self._attr_is_on = wand.led_on
        self._attr_rgb_color = wand.led_rgb

    async def async_added_to_hass(self) -> None:
        """Register state update callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_LED.format(self.entry.entry_id),
                self._async_on_led_changed,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_CONNECTED.format(self.entry.entry_id),
                self._async_on_connected_changed,
            )
        )

    @callback
    def _async_on_led_changed(
        self, is_on: bool, rgb: tuple[int, int, int]
    ) -> None:
        """Update LED state."""
        self._attr_is_on = is_on
        self._attr_rgb_color = rgb
        self.async_write_ha_state()

    @callback
    def _async_on_connected_changed(self, connected: bool) -> None:
        """Reset LED state if wand disconnects."""
        if not connected:
            self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the wand LED with optional RGB color."""
        rgb: tuple[int, int, int] | None = kwargs.get(ATTR_RGB_COLOR)
        await self.wand.set_led(True, rgb=rgb)
        self._attr_is_on = self.wand.led_on
        self._attr_rgb_color = self.wand.led_rgb
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the wand LED."""
        await self.wand.set_led(False)
        self._attr_is_on = False
        self.async_write_ha_state()
