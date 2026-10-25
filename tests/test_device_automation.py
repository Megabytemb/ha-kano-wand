"""Tests for Kano Wand device triggers, actions, conditions, and logbook integration."""
from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.kano_wand import async_setup_entry, async_unload_entry
from custom_components.kano_wand.const import (
    CHAR_LED,
    CHAR_QUATERNIONS_RESET,
    CHAR_VIBRATOR,
    DOMAIN,
    EVENT_KANO_WAND_SPELL,
    EVENT_KANO_WAND_STATUS,
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
from custom_components.kano_wand.logbook import async_describe_events


async def test_device_triggers_list_and_attach(hass) -> None:
    """Verify all 31 device triggers (6 general + 25 individual spells) are exposed and attach cleanly."""
    triggers = await async_get_triggers(hass, "dev_wand_1")
    assert len(triggers) == 6 + len(REAL_SPELLS) == 31

    spell_subtypes = [
        t["subtype"] for t in triggers if t["type"] == "spell_cast"
    ]
    assert spell_subtypes == REAL_SPELLS

    from homeassistant.components.homeassistant.triggers import event as event_trigger

    event_trigger.async_attach_trigger.reset_mock()
    action = AsyncMock()
    trigger_info = {"trigger_id": "test"}

    # 1. Specific spell trigger ("Lumos")
    await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "spell_cast",
            "subtype": "Lumos",
        },
        action,
        trigger_info,
    )
    attached_cfg = event_trigger.async_attach_trigger.call_args.args[1]
    assert attached_cfg["event_type"] == EVENT_KANO_WAND_SPELL
    assert attached_cfg["event_data"] == {
        "device_id": "dev_wand_1",
        "spell": "Lumos",
    }

    # 2. Any spell trigger
    await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "any_spell",
        },
        action,
        trigger_info,
    )
    attached_cfg = event_trigger.async_attach_trigger.call_args.args[1]
    assert attached_cfg["event_type"] == EVENT_KANO_WAND_SPELL
    assert attached_cfg["event_data"] == {
        "device_id": "dev_wand_1",
        "is_spell": True,
    }

    # 3. Button pressed status trigger
    await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "dev_wand_1",
            "type": "button_pressed",
        },
        action,
        trigger_info,
    )
    attached_cfg = event_trigger.async_attach_trigger.call_args.args[1]
    assert attached_cfg["event_type"] == EVENT_KANO_WAND_STATUS
    assert attached_cfg["event_data"] == {
        "device_id": "dev_wand_1",
        "type": "button_pressed",
    }


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
    assert len(actions) == 11

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

        # Device actions: vibrate_burst, led_turn_on, led_turn_off, recentre, disconnect
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


def test_logbook_event_descriptions(hass) -> None:
    """Verify logbook.py formats spell and recentre events for the Device Activity panel."""
    registered: dict[tuple[str, str], Any] = {}

    def _register(domain: str, event_name: str, callback_fn: Any) -> None:
        registered[(domain, event_name)] = callback_fn

    async_describe_events(hass, _register)
    describe_fn = registered[(DOMAIN, EVENT_KANO_WAND_SPELL)]

    lumos_event = types.SimpleNamespace(
        data={
            "device_id": "dev_wand_1",
            "name": "Kano-Wand-75",
            "spell": "Lumos",
            "score": 0.962,
        }
    )
    assert describe_fn(lumos_event) == {
        "name": "Kano-Wand-75",
        "message": "cast Lumos (96% confidence)",
        "device_id": "dev_wand_1",
    }

    recentre_event = types.SimpleNamespace(
        data={
            "device_id": "dev_wand_1",
            "name": "Kano-Wand-75",
            "spell": "recentre",
            "score": 1.0,
        }
    )
    assert describe_fn(recentre_event) == {
        "name": "Kano-Wand-75",
        "message": "recentered its orientation",
        "device_id": "dev_wand_1",
    }
