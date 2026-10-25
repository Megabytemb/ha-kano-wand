"""Button platform for Kano Wand controls."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand button entities."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            KanoWandVibrateButton(entry, wand),
            KanoWandRecentreButton(entry, wand),
            KanoWandDisconnectButton(entry, wand),
        ]
    )


class KanoWandVibrateButton(KanoWandBaseEntity, ButtonEntity):
    """Button entity to vibrate the Kano Wand using the selected pattern."""

    _attr_name = "Vibrate"
    _attr_icon = "mdi:vibrate"

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the vibrate button."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_vibrate"

    async def async_press(self) -> None:
        """Trigger the currently selected vibration pattern on the wand."""
        await self.wand.vibrate(self.wand.vibration_pattern)


class KanoWandRecentreButton(KanoWandBaseEntity, ButtonEntity):
    """Button entity to reset/recentre the wand's quaternion orientation."""

    _attr_name = "Recentre Orientation"
    _attr_icon = "mdi:compass-outline"

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the recentre button."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_recentre"

    async def async_press(self) -> None:
        """Reset the wand's internal quaternion orientation origin."""
        await self.wand.reset_position()


class KanoWandDisconnectButton(KanoWandBaseEntity, ButtonEntity):
    """Button entity to immediately disconnect the BLE session."""

    _attr_name = "Disconnect"
    _attr_icon = "mdi:bluetooth-off"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the disconnect button."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_disconnect"

    async def async_press(self) -> None:
        """Immediately disconnect from the wand."""
        await self.wand.disconnect()
