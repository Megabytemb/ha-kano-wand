"""Sensor platform for Kano Wand."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_TYPE_RECENTRE, SIGNAL_WAND_SPELL, SIGNAL_WAND_TEMP
from .entity import KanoWandBaseEntity
from .wand import KanoWand


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kano Wand sensors."""
    wand: KanoWand = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            KanoWandSpellSensor(entry, wand),
            KanoWandSpellConfidenceSensor(entry, wand),
            KanoWandTemperatureSensor(entry, wand),
        ]
    )


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


class KanoWandSpellConfidenceSensor(KanoWandBaseEntity, SensorEntity):
    """Sensor for the confidence percentage of the last recognized spell."""

    _attr_name = "Last Spell Confidence"
    _attr_icon = "mdi:bullseye-arrow"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the confidence sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_last_spell_confidence"
        self._state: float | None = None
        self._attrs: dict[str, Any] = {}

    @property
    def native_value(self) -> float | None:
        """Return the confidence percentage (0-100)."""
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
        """Update the spell confidence state."""
        spell = spell_data.get("spell")
        if spell == EVENT_TYPE_RECENTRE:
            return
        score = float(spell_data.get("score") or 0.0)
        self._state = round(score * 100.0, 1)
        self._attrs = {
            "spell": spell,
            "score": score,
            "duration": spell_data.get("duration"),
            "points": spell_data.get("points"),
        }
        self.async_write_ha_state()


class KanoWandTemperatureSensor(KanoWandBaseEntity, SensorEntity):
    """Diagnostic sensor for the Kano Wand's onboard IMU temperature."""

    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, wand: KanoWand) -> None:
        """Initialize the temperature sensor."""
        super().__init__(entry, wand)
        self._attr_unique_id = f"{entry.entry_id}_temperature"
        self._state: float | None = wand.temperature

    @property
    def native_value(self) -> float | None:
        """Return the temperature in Celsius."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Subscribe to temperature dispatcher updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WAND_TEMP.format(self.entry.entry_id),
                self._update_temperature,
            )
        )

    @callback
    def _update_temperature(self, temperature: float) -> None:
        """Update the temperature state."""
        self._state = temperature
        self.async_write_ha_state()
