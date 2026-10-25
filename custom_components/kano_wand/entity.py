"""Base entity for the Kano Wand integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .wand import KanoWand


class KanoWandBaseEntity(Entity):
    """Base class for Kano Wand entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the base entity."""
        super().__init__()
        self.entry = entry
        self.wand = wand
        address = entry.data[CONF_ADDRESS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            name=entry.title or "Kano Wand",
            manufacturer=wand.organization or "Kano",
            model="Kano Coding Wand",
            sw_version=wand.software_version,
            hw_version=wand.hardware_version,
        )
