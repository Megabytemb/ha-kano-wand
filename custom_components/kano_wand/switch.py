"""Switch platform for Kano Wand."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand switches."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KanoWandAutoConnectSwitch(entry, wand)])


class KanoWandAutoConnectSwitch(KanoWandBaseEntity, SwitchEntity, RestoreEntity):
    """Switch to enable or disable automatic BLE connection to the wand.

    Turn this switch off to immediately disconnect Home Assistant from the wand
    and prevent background reconnection (for example, while testing locally on a PC).
    """

    _attr_name = "Auto Connect"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the switch."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_auto_connect"
        self._attr_is_on = wand.auto_connect

    async def async_added_to_hass(self) -> None:
        """Restore previous switch state on Home Assistant startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in ("on", "off"):
                is_on = last_state.state == "on"
                self._attr_is_on = is_on
                self.wand.auto_connect = is_on
                if not is_on and self.wand.is_connected:
                    await self.wand.disconnect()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-connect and connect if the wand is awake."""
        self._attr_is_on = True
        self.wand.auto_connect = True
        self.async_write_ha_state()
        await self.wand.ensure_connected()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-connect and immediately disconnect from the wand."""
        self._attr_is_on = False
        self.wand.auto_connect = False
        self.async_write_ha_state()
        await self.wand.disconnect()
