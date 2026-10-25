"""Fixtures for Kano Wand tests."""
import pytest
from unittest.mock import MagicMock

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield

@pytest.fixture
def mock_bluetooth_service_info():
    """Mock bluetooth service info."""
    return BluetoothServiceInfoBleak(
        name="Kano-Wand-Test",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={1: b"\x01\x02"},
        service_data={},
        service_uuids=[],
        source="local",
        device=MagicMock(),
        advertisement=MagicMock(),
    )
