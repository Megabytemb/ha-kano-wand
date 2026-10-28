"""The Kano Wand integration."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_PATTERN,
    DOMAIN,
    SERVICE_VIBRATE,
    SIGNAL_WAND_BATTERY,
    SIGNAL_WAND_BUTTON,
    SIGNAL_WAND_CONNECTED,
    SIGNAL_WAND_DRAW,
    SIGNAL_WAND_FLICK,
    SIGNAL_WAND_LED,
    SIGNAL_WAND_SPELL,
    SIGNAL_WAND_TEMP,
    VIBRATION_PATTERNS,
    VIBRATION_REGULAR,
)
from .gesture import GestureSpells
from .wand import KanoWand

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.SWITCH,
    Platform.SELECT,
]

SERVICE_VIBRATE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_PATTERN, default="regular"): vol.Any(
            vol.In(list(VIBRATION_PATTERNS.keys())),
            vol.All(vol.Coerce(int), vol.Range(min=1, max=7)),
        ),
    }
)


def _clear_ble_advertisement_history(address: str) -> None:
    """Clear habluetooth's cached advertisement history for the wand's MAC address.

    Because the Kano Wand broadcasts a static advertisement payload (its name,
    service UUIDs, and manufacturer data never change), habluetooth's duplicate
    advertisement filter (`_scanner_adv_received`) would otherwise ignore wake-up
    advertisements for up to 15 minutes after a disconnect.
    """
    with contextlib.suppress(Exception):
        from habluetooth import get_manager

        manager = get_manager()
        if manager is None:
            return
        if hasattr(manager, "async_clear_advertisement_history"):
            manager.async_clear_advertisement_history(address)
        else:
            if hasattr(manager, "_all_history"):
                manager._all_history.pop(address, None)
            if hasattr(manager, "_connectable_history"):
                manager._connectable_history.pop(address, None)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kano Wand from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    # Load the TFLite gesture model in an executor thread to avoid blocking the event loop
    gesture_spells = GestureSpells(load_immediately=False)
    await hass.async_add_executor_job(gesture_spells.loadModel)

    @callback
    def _on_button(pressed: bool) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_BUTTON.format(entry.entry_id), pressed
        )

    @callback
    def _on_spell(spell_data: dict[str, Any]) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_SPELL.format(entry.entry_id), spell_data
        )
        # If invoked directly (e.g. in tests) without going through _on_draw, also update image
        if "recognized" not in spell_data:
            async_dispatcher_send(
                hass, SIGNAL_WAND_DRAW.format(entry.entry_id), spell_data
            )

    @callback
    def _on_draw(draw_data: dict[str, Any]) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_DRAW.format(entry.entry_id), draw_data
        )

    @callback
    def _on_flick(flick_data: dict[str, Any]) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_FLICK.format(entry.entry_id), flick_data
        )

    @callback
    def _on_battery(battery_low: bool) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_BATTERY.format(entry.entry_id), battery_low
        )

    @callback
    def _on_temperature(temperature: float) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_TEMP.format(entry.entry_id), temperature
        )

    @callback
    def _on_connected(connected: bool) -> None:
        if not connected:
            _clear_ble_advertisement_history(address)
        async_dispatcher_send(
            hass, SIGNAL_WAND_CONNECTED.format(entry.entry_id), connected
        )

    @callback
    def _on_led(led_on: bool, rgb: tuple[int, int, int]) -> None:
        async_dispatcher_send(
            hass, SIGNAL_WAND_LED.format(entry.entry_id), led_on, rgb
        )

    @callback
    def _on_device_info(sw_version: str | None, hw_version: str | None) -> None:
        dev_reg = dr.async_get(hass)
        if device := dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)}):
            dev_reg.async_update_device(
                device.id,
                sw_version=sw_version,
                hw_version=hw_version,
            )

    def _get_ble_device() -> Any:
        """Fetch the freshest BLEDevice routed via the closest proxy or adapter."""
        return bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )

    wand = KanoWand(
        ble_device_callback=_get_ble_device,
        name=entry.title or f"Kano Wand ({address})",
        on_button=_on_button,
        on_spell=_on_spell,
        on_draw=_on_draw,
        on_flick=_on_flick,
        on_connected=_on_connected,
        on_led=_on_led,
        on_battery=_on_battery,
        on_temperature=_on_temperature,
        on_device_info=_on_device_info,
        gesture_spells=gesture_spells,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = wand

    # Clean up legacy battery sensor entity (Kano Wand hardware uses 2x AAA batteries
    # without a fuel gauge IC and always reports 0% on its battery characteristic)
    ent_reg = er.async_get(hass)
    if old_batt_entity_id := ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{entry.entry_id}_battery"
    ):
        ent_reg.async_remove(old_batt_entity_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_trigger_connect(service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Schedule a background BLE connection when an advertisement is heard."""
        if wand.auto_connect and not wand.is_connected and not wand.is_connecting:
            _LOGGER.debug(
                "Advertisement received for %s via %s (RSSI %s); scheduling connection",
                address,
                service_info.source,
                service_info.rssi,
            )
            entry.async_create_background_task(
                hass,
                wand.ensure_connected(service_info.device),
                f"kano_wand_connect_{entry.entry_id}",
            )

    @callback
    def _async_on_ble_advertisement(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Reconnect automatically when the wand wakes up in range of any proxy."""
        _async_trigger_connect(service_info)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_ble_advertisement,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    # Also subscribe to raw per-packet advertisements on habluetooth's manager if available.
    # This fires before habluetooth's unchanged-payload deduplication guard, ensuring
    # instant reconnection whenever the wand button is pressed to wake it up.
    with contextlib.suppress(Exception):
        from habluetooth import get_manager

        manager = get_manager()
        if manager is not None and hasattr(
            manager, "async_register_advertisement_callback"
        ):
            entry.async_on_unload(
                manager.async_register_advertisement_callback(
                    _async_trigger_connect, address
                )
            )

    # Attempt an initial connection in the background if the wand is already awake
    if wand.auto_connect and _get_ble_device() is not None:
        entry.async_create_background_task(
            hass,
            wand.ensure_connected(),
            f"kano_wand_initial_connect_{entry.entry_id}",
        )

    _async_register_services(hass)
    return True


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_VIBRATE):
        return

    async def _async_handle_vibrate(call: ServiceCall) -> None:
        """Handle the kano_wand.vibrate service call."""
        pattern = call.data.get(ATTR_PATTERN, VIBRATION_REGULAR)
        device_ids: list[str] | None = call.data.get(ATTR_DEVICE_ID)
        wands_by_entry: dict[str, KanoWand] = hass.data.get(DOMAIN, {})

        target_wands: list[KanoWand] = []
        if device_ids:
            dev_reg = dr.async_get(hass)
            for dev_id in device_ids:
                device = dev_reg.async_get(dev_id)
                if not device:
                    continue
                for entry_id in device.config_entries:
                    if entry_id in wands_by_entry:
                        target_wands.append(wands_by_entry[entry_id])
        else:
            target_wands = list(wands_by_entry.values())

        for wand in target_wands:
            try:
                await wand.vibrate(pattern)
            except Exception as ex:
                _LOGGER.warning("Failed to vibrate %s: %s", wand.name, ex)

    hass.services.async_register(
        DOMAIN,
        SERVICE_VIBRATE,
        _async_handle_vibrate,
        schema=SERVICE_VIBRATE_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        wand: KanoWand | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if wand is not None:
            await wand.disconnect()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_VIBRATE)

    return unload_ok
