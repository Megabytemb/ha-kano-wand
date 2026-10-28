"""Binary sensor platform for Kano Wand."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SIGNAL_WAND_BATTERY,
    SIGNAL_WAND_BUTTON,
    SIGNAL_WAND_CONNECTED,
)
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand binary sensors."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            KanoWandButtonSensor(entry, wand),
            KanoWandConnectedSensor(entry, wand),
            KanoWandBatterySensor(entry, wand),
        ]
    )


class KanoWandButtonSensor(KanoWandBaseEntity, BinarySensorEntity):
    """Binary sensor for the wand button."""

    _attr_name = "Button"
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_button"
        self._attr_is_on = wand.button_pressed

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_BUTTON.format(self.entry.entry_id),
                self._update_button,
            )
        )

    @callback
    def _update_button(self, pressed: bool) -> None:
        """Update the button state."""
        self._attr_is_on = pressed
        self.async_write_ha_state()


class KanoWandConnectedSensor(KanoWandBaseEntity, BinarySensorEntity):
    """Binary sensor indicating whether the wand is actively connected via BLE."""

    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_connected"
        self._attr_is_on = wand.is_connected

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_CONNECTED.format(self.entry.entry_id),
                self._update_connected,
            )
        )

    @callback
    def _update_connected(self, connected: bool) -> None:
        """Update the connectivity state."""
        self._attr_is_on = connected
        self.async_write_ha_state()


class KanoWandBatterySensor(KanoWandBaseEntity, BinarySensorEntity):
    """Binary sensor for the wand's low-battery flag (0 = Normal, 1 = Low)."""

    _attr_name = "Battery"
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the battery binary sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_battery_low"
        self._attr_is_on = wand.battery_low

    async def async_added_to_hass(self) -> None:
        """Subscribe to battery flag updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_BATTERY.format(self.entry.entry_id),
                self._update_battery,
            )
        )

    @callback
    def _update_battery(self, battery_low: bool) -> None:
        """Update the low-battery state."""
        self._attr_is_on = battery_low
        self.async_write_ha_state()
