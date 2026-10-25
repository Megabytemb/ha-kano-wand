"""Test the Kano Wand config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kano_wand.const import DOMAIN

async def test_bluetooth_discovery(hass: HomeAssistant, mock_bluetooth_service_info) -> None:
    """Test bluetooth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=mock_bluetooth_service_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "custom_components.kano_wand.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kano-Wand-Test"
    assert result["data"] == {
        "address": "AA:BB:CC:DD:EE:FF",
    }
    assert len(mock_setup.mock_calls) == 1

async def test_user_flow(hass: HomeAssistant, mock_bluetooth_service_info) -> None:
    """Test user-initiated flow."""
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[mock_bluetooth_service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.kano_wand.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "AA:BB:CC:DD:EE:FF"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "address": "AA:BB:CC:DD:EE:FF",
    }
