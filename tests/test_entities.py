"""Tests for Home Assistant Kano Wand integration setup, entities, and BLE lifecycle."""
from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)

from custom_components.kano_wand import async_setup_entry, async_unload_entry
from custom_components.kano_wand.const import (
    CHAR_LED,
    CHAR_QUATERNIONS_RESET,
    CHAR_VIBRATOR,
    DOMAIN,
    SERVICE_VIBRATE,
)
from custom_components.kano_wand.diagnostics import async_get_config_entry_diagnostics


EXPECTED_ENTITY_IDS = {
    "entry_123_last_spell",
    "entry_123_last_spell_confidence",
    "entry_123_button",
    "entry_123_connected",
    "entry_123_spell_event",
    "entry_123_led",
    "entry_123_keep_alive_timeout",
    "entry_123_min_spell_confidence",
    "entry_123_vibrate",
    "entry_123_recentre",
    "entry_123_disconnect",
    "entry_123_last_spell_drawing",
    "entry_123_auto_connect",
    "entry_123_vibrate_on_connect",
    "entry_123_vibrate_on_spell",
    "entry_123_vibration_pattern",
}


async def test_setup_while_wand_asleep_and_unload(hass, config_entry) -> None:
    """Verify async_setup_entry succeeds when wand is asleep, cleans up legacy battery, and registers all 9 entities."""
    mock_er = MagicMock()
    mock_er.async_get_entity_id.return_value = "sensor.kano_wand_battery"
    hass._entity_registry = mock_er

    assert await async_setup_entry(hass, config_entry) is True
    mock_er.async_remove.assert_called_once_with("sensor.kano_wand_battery")
    assert set(hass.entities.keys()) == EXPECTED_ENTITY_IDS
    assert hass.entities["entry_123_connected"].is_on is False
    assert hass.entities["entry_123_auto_connect"].is_on is True

    assert await async_unload_entry(hass, config_entry) is True
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_ble_proxy_advertisement_connects_and_vibrates(
    hass, config_entry, fake_ble_client, fake_ble_device
) -> None:
    """Verify BLE advertisement triggers connection, burst welcome vibrate, and auto_connect switch."""
    await async_setup_entry(hass, config_entry)
    hass.ble_device = fake_ble_device

    with patch(
        "custom_components.kano_wand.wand.establish_connection",
        new=AsyncMock(return_value=fake_ble_client),
    ) as mock_establish:
        service_info = BluetoothServiceInfoBleak(
            name="Kano-Wand-75",
            address="AA:BB:CC:DD:EE:FF",
            rssi=-55,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="living_room_ble_proxy",
            device=fake_ble_device,
            advertisement=MagicMock(),
        )
        for cb in hass.ble_callbacks:
            cb(service_info, BluetoothChange.ADVERTISEMENT)

        await asyncio.gather(*config_entry.background_tasks)
        wand = hass.data[DOMAIN][config_entry.entry_id]
        if wand._background_tasks:
            await asyncio.gather(*list(wand._background_tasks))

        assert mock_establish.await_count == 1
        assert hass.entities["entry_123_connected"].is_on is True

        vibrate_calls = [
            c
            for c in fake_ble_client.write_gatt_char.call_args_list
            if c.args[0] == CHAR_VIBRATOR and c.args[1] == bytearray([3])
        ]
        assert len(vibrate_calls) == 1

        # Turning off Auto Connect disconnects the wand and blocks advertisement reconnects
        auto_connect_switch = hass.entities["entry_123_auto_connect"]
        await auto_connect_switch.async_turn_off()
        assert auto_connect_switch.is_on is False
        assert wand.auto_connect is False
        assert hass.entities["entry_123_connected"].is_on is False

        for cb in hass.ble_callbacks:
            cb(service_info, BluetoothChange.ADVERTISEMENT)
        assert mock_establish.await_count == 1

        # Turning Auto Connect back on reconnects immediately
        await auto_connect_switch.async_turn_on()
        assert auto_connect_switch.is_on is True
        assert wand.auto_connect is True
        assert mock_establish.await_count == 2
        assert hass.entities["entry_123_connected"].is_on is True

    await async_unload_entry(hass, config_entry)


async def test_keep_alive_timeout_number_slider(hass, config_entry) -> None:
    """Verify Keep-Alive Timeout NumberEntity updates wand timeout dynamically."""
    await async_setup_entry(hass, config_entry)
    timeout_entity = hass.entities["entry_123_keep_alive_timeout"]
    await timeout_entity.async_set_native_value(5.5)

    wand = hass.data[DOMAIN][config_entry.entry_id]
    assert wand.keep_alive_timeout_minutes == 5.5
    await async_unload_entry(hass, config_entry)


async def test_led_light_entity_and_vibrate_controls(
    hass, config_entry, fake_ble_client, fake_ble_device
) -> None:
    """Verify RGB LED LightEntity (RGB565) and Vibrate ButtonEntity / service."""
    await async_setup_entry(hass, config_entry)
    hass.ble_device = fake_ble_device
    wand = hass.data[DOMAIN][config_entry.entry_id]

    with patch(
        "custom_components.kano_wand.wand.establish_connection",
        new=AsyncMock(return_value=fake_ble_client),
    ):
        await wand.ensure_connected()
        if wand._background_tasks:
            await asyncio.gather(*list(wand._background_tasks))

        led_entity = hass.entities["entry_123_led"]
        await led_entity.async_turn_on(rgb_color=(255, 0, 128))
        assert led_entity.is_on is True
        assert led_entity.rgb_color == (255, 0, 128)
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_LED, bytearray([1, 248, 16]), True
        )

        await led_entity.async_turn_off()
        assert led_entity.is_on is False

        vibrate_btn = hass.entities["entry_123_vibrate"]
        await vibrate_btn.async_press()
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_VIBRATOR, bytearray([1]), True
        )

        await hass.services.async_call(DOMAIN, SERVICE_VIBRATE, {"pattern": "burst"})
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_VIBRATOR, bytearray([3]), True
        )

        # Select entity changes vibration pattern & previews immediately on wand
        pattern_select = hass.entities["entry_123_vibration_pattern"]
        assert pattern_select.current_option == "regular"
        await pattern_select.async_select_option("short_long")
        assert pattern_select.current_option == "short_long"
        assert wand.vibration_pattern == "short_long"
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_VIBRATOR, bytearray([5]), True
        )

        # Pressing Vibrate button now uses the selected "short_long" (5) pattern
        fake_ble_client.write_gatt_char.reset_mock()
        await vibrate_btn.async_press()
        fake_ble_client.write_gatt_char.assert_called_once_with(
            CHAR_VIBRATOR, bytearray([5]), True
        )

        # Recentre button writes CHAR_QUATERNIONS_RESET
        recentre_btn = hass.entities["entry_123_recentre"]
        await recentre_btn.async_press()
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_QUATERNIONS_RESET, bytearray([1]), True
        )

        # Diagnostics export
        diag = await async_get_config_entry_diagnostics(hass, config_entry)
        assert diag["is_connected"] is True
        assert diag["vibration_pattern"] == "short_long"

        # Disconnect button disconnects immediately
        disconnect_btn = hass.entities["entry_123_disconnect"]
        await disconnect_btn.async_press()
        assert hass.entities["entry_123_connected"].is_on is False

    await async_unload_entry(hass, config_entry)


async def test_spell_events_sensor_image_and_quaternion_stream(
    hass, config_entry, fake_ble_client
) -> None:
    """Verify repeated spell casts, short-click recentre, and raw GATT quaternion streaming."""
    await async_setup_entry(hass, config_entry)
    wand = hass.data[DOMAIN][config_entry.entry_id]

    spell_sensor = hass.entities["entry_123_last_spell"]
    confidence_sensor = hass.entities["entry_123_last_spell_confidence"]
    spell_event = hass.entities["entry_123_spell_event"]
    spell_image = hass.entities["entry_123_last_spell_drawing"]
    button_sensor = hass.entities["entry_123_button"]

    wand._on_button_notification(None, bytearray([1]))
    assert button_sensor.is_on is True

    lumos_points = [[300 + i * 5, 500 - i * 15] for i in range(15)] + [
        [375 + i * 5, 275 + i * 15] for i in range(15)
    ]
    payload = {
        "spell": "Lumos",
        "score": 0.96,
        "duration": 0.85,
        "points": len(lumos_points),
        "positions": lumos_points,
    }
    wand.on_spell_cb(payload)
    wand.on_spell_cb(payload)
    assert spell_event.last_event_type == "Lumos"
    assert spell_sensor.native_value == "Lumos"
    assert confidence_sensor.native_value == 96.0
    assert spell_image.extra_state_attributes["spell"] == "Lumos"

    # Short click (<0.2s) triggers recentre on EventEntity while keeping Last Spell sensor
    wand._on_button_notification(None, bytearray([0]))
    assert button_sensor.is_on is False
    assert spell_event.last_event_type == "recentre"
    assert spell_sensor.native_value == "Lumos"

    # Raw GATT quaternion stream -> button release -> PNG render
    wand._on_button_notification(None, bytearray([1]))
    wand._time_button_down -= 0.65
    for i in range(16):
        pkt = bytearray(struct.pack("<hhhh", int(-400 + 50 * i), int(20 * i), 1000, 0))
        wand._on_motion_notification(None, pkt)
    assert len(wand.current_spell) == 16
    wand._on_button_notification(None, bytearray([0]))

    png_bytes = await spell_image.async_image()
    assert png_bytes is not None and png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    wand._on_disconnected(fake_ble_client)
    assert hass.entities["entry_123_connected"].is_on is False
    assert hass.entities["entry_123_led"].is_on is False

    await async_unload_entry(hass, config_entry)
