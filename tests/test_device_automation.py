"""Tests for Kano Wand device triggers, actions, and conditions."""
from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.kano_wand import async_setup_entry, async_unload_entry
from custom_components.kano_wand.const import (
    CHAR_LED,
    CHAR_QUATERNIONS_RESET,
    CHAR_VIBRATOR,
    DOMAIN,
    REAL_SPELLS,
)
from custom_components.kano_wand.device_action import (
    async_call_action_from_config,
    async_get_actions,
)
from custom_components.kano_wand.device_condition import (
    async_condition_from_config,
    async_get_conditions,
)
from custom_components.kano_wand.device_trigger import (
    async_attach_trigger,
    async_get_triggers,
)


async def test_device_triggers_list_and_fire(hass, config_entry) -> None:
    """Verify all 31 device triggers attach via internal dispatcher signals with zero event bus spam."""
    mock_dr = MagicMock()
    mock_dr.async_get.return_value = types.SimpleNamespace(
        id="dev_wand_1", config_entries=[config_entry.entry_id]
    )
    hass._device_registry = mock_dr

    await async_setup_entry(hass, config_entry)
    wand = hass.data[DOMAIN][config_entry.entry_id]

    triggers = await async_get_triggers(hass, "dev_wand_1")
    assert len(triggers) == 10 + len(REAL_SPELLS) == 35
    assert [t["subtype"] for t in triggers if t["type"] == "spell_cast"] == REAL_SPELLS

    fired_lumos: list[dict] = []
    fired_any_spell: list[dict] = []
    fired_button: list[dict] = []
    fired_flick_up: list[dict] = []

    unsub_lumos = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "spell_cast",
            "subtype": "Lumos",
        },
        lambda payload: fired_lumos.append(payload),
        {"trigger_data": {"id": "lumos_trig"}},
    )
    unsub_any = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "any_spell",
        },
        lambda payload: fired_any_spell.append(payload),
        {"trigger_data": {"id": "any_trig"}},
    )
    unsub_btn = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "button_pressed",
        },
        lambda payload: fired_button.append(payload),
        {"trigger_data": {"id": "btn_trig"}},
    )
    unsub_flick = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "flick_up",
        },
        lambda payload: fired_flick_up.append(payload),
        {"trigger_data": {"id": "flick_trig"}},
    )

    # Casting Lumos twice in a row fires both times
    wand.on_spell_cb({"spell": "Lumos", "score": 0.96, "duration": 0.8, "points": 28})
    wand.on_spell_cb({"spell": "Lumos", "score": 0.91, "duration": 0.7, "points": 25})
    assert len(fired_lumos) == 2
    assert fired_lumos[0]["trigger"]["spell"] == "Lumos"
    assert fired_lumos[0]["trigger"]["score"] == 0.96
    assert len(fired_any_spell) == 2

    # Short-click recentre does NOT fire any_spell or spell_cast: Lumos
    wand.on_spell_cb({"spell": "recentre", "score": 1.0, "duration": 0.08, "points": 0})
    assert len(fired_lumos) == 2
    assert len(fired_any_spell) == 2

    # Button press fires button_pressed trigger
    wand.on_button_cb(True)
    wand.on_button_cb(False)
    assert len(fired_button) == 1

    # Flick up fires flick_up trigger (and ignores flick_down)
    wand.on_flick_cb({"direction": "down", "intensity": 120.0})
    assert len(fired_flick_up) == 0
    wand.on_flick_cb({"direction": "up", "intensity": 185.0})
    assert len(fired_flick_up) == 1
    assert fired_flick_up[0]["trigger"]["direction"] == "up"

    # No custom events were dumped onto hass.bus
    assert len(hass.bus.events) == 0

    unsub_lumos()
    unsub_any()
    unsub_btn()
    unsub_flick()
    await async_unload_entry(hass, config_entry)


async def test_device_actions_and_conditions(
    hass, config_entry, fake_ble_client, fake_ble_device
) -> None:
    """Verify device actions and device conditions operate on the active KanoWand."""
    mock_dr = MagicMock()
    mock_dr.async_get.return_value = types.SimpleNamespace(
        id="dev_wand_1", config_entries=[config_entry.entry_id]
    )
    hass._device_registry = mock_dr

    await async_setup_entry(hass, config_entry)
    hass.ble_device = fake_ble_device
    wand = hass.data[DOMAIN][config_entry.entry_id]

    actions = await async_get_actions(hass, "dev_wand_1")
    assert len(actions) == 12

    conditions = await async_get_conditions(hass, "dev_wand_1")
    assert len(conditions) == 3

    is_conn_fn = async_condition_from_config(
        hass, {"device_id": "dev_wand_1", "type": "is_connected"}
    )
    is_disconn_fn = async_condition_from_config(
        hass, {"device_id": "dev_wand_1", "type": "is_disconnected"}
    )
    is_btn_fn = async_condition_from_config(
        hass, {"device_id": "dev_wand_1", "type": "is_button_pressed"}
    )

    assert is_conn_fn(hass, None) is False
    assert is_disconn_fn(hass, None) is True
    assert is_btn_fn(hass, None) is False

    with patch(
        "custom_components.kano_wand.wand.establish_connection",
        new=AsyncMock(return_value=fake_ble_client),
    ):
        await wand.ensure_connected()
        assert is_conn_fn(hass, None) is True
        assert is_disconn_fn(hass, None) is False

        wand.button_pressed = True
        assert is_btn_fn(hass, None) is True

        fake_ble_client.write_gatt_char.reset_mock()
        await async_call_action_from_config(
            hass,
            {"device_id": "dev_wand_1", "type": "vibrate_burst"},
            {},
            None,
        )
        fake_ble_client.write_gatt_char.assert_called_once_with(
            CHAR_VIBRATOR, bytearray([3]), True
        )

        await async_call_action_from_config(
            hass,
            {"device_id": "dev_wand_1", "type": "led_turn_on"},
            {},
            None,
        )
        assert wand.led_on is True

        await async_call_action_from_config(
            hass,
            {"device_id": "dev_wand_1", "type": "led_turn_off"},
            {},
            None,
        )
        assert wand.led_on is False
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_LED, bytearray([0, 0, 0]), True
        )

        await async_call_action_from_config(
            hass,
            {"device_id": "dev_wand_1", "type": "recentre"},
            {},
            None,
        )
        fake_ble_client.write_gatt_char.assert_any_call(
            CHAR_QUATERNIONS_RESET, bytearray([1]), True
        )

        await async_call_action_from_config(
            hass,
            {"device_id": "dev_wand_1", "type": "disconnect"},
            {},
            None,
        )
        assert wand.is_connected is False

    await async_unload_entry(hass, config_entry)
