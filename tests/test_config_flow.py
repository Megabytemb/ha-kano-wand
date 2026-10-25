"""Tests for the Kano Wand Bluetooth and User Config Flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from custom_components.kano_wand.config_flow import KanoWandConfigFlow, _is_kano_wand
from custom_components.kano_wand.const import SERVICE_INFO


def _make_discovery_info(
    name: str = "Kano-Wand-75",
    address: str = "AA:BB:CC:DD:EE:FF",
    service_uuids: list[str] | None = None,
) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=service_uuids or [SERVICE_INFO.lower()],
        source="local",
        device=MagicMock(),
        advertisement=MagicMock(),
    )


def test_is_kano_wand_matcher() -> None:
    """Verify _is_kano_wand matches by local_name prefix or Kano GATT service UUID."""
    assert _is_kano_wand(_make_discovery_info(name="Kano-Wand-11-c9-05", service_uuids=[])) is True
    assert _is_kano_wand(_make_discovery_info(name="Unknown", service_uuids=[SERVICE_INFO])) is True
    assert _is_kano_wand(_make_discovery_info(name="Other-BLE", service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"])) is False


async def test_bluetooth_discovery_and_confirm_flow(hass) -> None:
    """Test automatic Bluetooth discovery step followed by user confirmation."""
    flow = KanoWandConfigFlow()
    flow.hass = hass
    discovery = _make_discovery_info(name="Kano-Wand-75", address="AA:BB:CC:DD:EE:FF")

    result = await flow.async_step_bluetooth(discovery)
    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"
    assert flow.unique_id == "AA:BB:CC:DD:EE:FF"

    result2 = await flow.async_step_bluetooth_confirm(user_input={})
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Kano-Wand-75"
    assert result2["data"] == {"address": "AA:BB:CC:DD:EE:FF"}


async def test_user_flow_discovery_and_no_devices(hass) -> None:
    """Test manual user flow when a wand is discovered and when no wand is in range."""
    flow = KanoWandConfigFlow()
    flow.hass = hass

    # 1. No devices in range -> aborts with no_devices_found
    result_empty = await flow.async_step_user()
    assert result_empty == {"type": "abort", "reason": "no_devices_found"}

    # 2. Device discovered -> shows selection form and creates entry
    flow2 = KanoWandConfigFlow()
    flow2.hass = hass
    discovery = _make_discovery_info(name="Kano-Wand-75", address="AA:BB:CC:DD:EE:FF")

    with patch(
        "custom_components.kano_wand.config_flow.async_discovered_service_info",
        return_value=[discovery],
    ):
        form_res = await flow2.async_step_user()
        assert form_res["type"] == "form"
        assert form_res["step_id"] == "user"

        entry_res = await flow2.async_step_user(
            user_input={"address": "AA:BB:CC:DD:EE:FF"}
        )
        assert entry_res["type"] == "create_entry"
        assert entry_res["title"] == "Kano-Wand-75"
        assert entry_res["data"] == {"address": "AA:BB:CC:DD:EE:FF"}
