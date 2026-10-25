"""Pytest configuration and shared fixtures for Kano Wand tests."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
from pathlib import Path
import sys
import types
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent


def _install_ha_stubs() -> None:
    """Install lightweight Home Assistant stubs so pytest runs on Windows, macOS, and Linux."""
    if "homeassistant" in sys.modules:
        return

    try:
        import voluptuous  # noqa: F401
    except ImportError:
        vol = types.ModuleType("voluptuous")
        vol.Schema = lambda s, **kw: s
        vol.Optional = lambda k, **kw: k
        vol.Required = lambda k, **kw: k
        vol.All = lambda *a: a
        vol.Any = lambda *a: a
        vol.In = lambda x: x
        vol.Coerce = lambda t: t
        vol.Range = lambda **kw: kw
        sys.modules["voluptuous"] = vol

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.const
    const = types.ModuleType("homeassistant.const")
    const.CONF_ADDRESS = "address"
    const.ATTR_DEVICE_ID = "device_id"
    const.PERCENTAGE = "%"

    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        EVENT = "event"
        LIGHT = "light"
        NUMBER = "number"
        BUTTON = "button"
        IMAGE = "image"
        SWITCH = "switch"
        SELECT = "select"

    class EntityCategory:
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    class UnitOfTime:
        MINUTES = "min"

    const.Platform = Platform
    const.EntityCategory = EntityCategory
    const.UnitOfTime = UnitOfTime
    sys.modules["homeassistant.const"] = const

    # homeassistant.core
    core = types.ModuleType("homeassistant.core")
    core.callback = lambda fn: fn

    class FakeBus:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, Any]]] = []

        def async_fire(self, event_type: str, event_data: dict[str, Any]) -> None:
            self.events.append((event_type, event_data))

    class FakeServices:
        def __init__(self) -> None:
            self._services: dict[tuple[str, str], Callable] = {}

        def has_service(self, domain: str, service: str) -> bool:
            return (domain, service) in self._services

        def async_register(
            self, domain: str, service: str, handler: Callable, schema: Any = None
        ) -> None:
            self._services[(domain, service)] = handler

        def async_remove(self, domain: str, service: str) -> None:
            self._services.pop((domain, service), None)

        async def async_call(
            self, domain: str, service: str, data: dict[str, Any]
        ) -> None:
            handler = self._services[(domain, service)]
            call = types.SimpleNamespace(data=data)
            await handler(call)

    class FakeConfigEntriesManager:
        def __init__(self, hass: FakeHomeAssistant) -> None:
            self.hass = hass
            self.forwarded_platforms: list[str] = []

        async def async_forward_entry_setups(
            self, entry: Any, platforms: list[str]
        ) -> None:
            self.forwarded_platforms.extend(platforms)
            for platform in platforms:
                mod = __import__(
                    f"custom_components.kano_wand.{platform}",
                    fromlist=["async_setup_entry"],
                )
                entities: list[Any] = []
                await mod.async_setup_entry(self.hass, entry, entities.extend)
                for ent in entities:
                    ent.hass = self.hass
                    await ent.async_added_to_hass()
                    self.hass.entities[ent.unique_id] = ent

        async def async_unload_platforms(
            self, entry: Any, platforms: list[str]
        ) -> bool:
            for ent in list(self.hass.entities.values()):
                for unsub in getattr(ent, "_unsubs", []):
                    unsub()
            self.hass.entities.clear()
            return True

    class FakeHomeAssistant:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}
            self.bus = FakeBus()
            self.services = FakeServices()
            self.config_entries = FakeConfigEntriesManager(self)
            self.entities: dict[str, Any] = {}
            self.dispatcher: dict[str, list[Callable]] = {}
            self.ble_callbacks: list[Callable] = []
            self.ble_device: Any = None

        async def async_add_executor_job(self, func: Callable, *args: Any) -> Any:
            return func(*args)

    core.HomeAssistant = FakeHomeAssistant
    core.ServiceCall = Any
    sys.modules["homeassistant.core"] = core

    # homeassistant.config_entries
    ce = types.ModuleType("homeassistant.config_entries")
    ce.ConfigFlowResult = dict[str, Any]
    ce.SOURCE_BLUETOOTH = "bluetooth"
    ce.SOURCE_USER = "user"

    class ConfigFlow:
        hass: Any = None
        unique_id: str | None = None

        def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

        def __new__(cls, *args: Any, **kwargs: Any) -> Any:
            instance = super().__new__(cls)
            instance.hass = None
            instance.context = {}
            instance.unique_id = None
            instance._existing_ids = set()
            return instance

        async def async_set_unique_id(
            self, unique_id: str, raise_on_progress: bool = True
        ) -> None:
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            if self.unique_id in self._existing_ids:
                raise RuntimeError("already_configured")

        def _async_current_ids(self) -> set[str]:
            return set(self._existing_ids)

        def _set_confirm_only(self) -> None:
            pass

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any = None,
            description_placeholders: dict[str, str] | None = None,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "description_placeholders": description_placeholders or {},
            }

        def async_create_entry(
            self, *, title: str, data: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
            }

        def async_abort(self, *, reason: str) -> dict[str, Any]:
            return {
                "type": "abort",
                "reason": reason,
            }

    ce.ConfigFlow = ConfigFlow

    @dataclass
    class FakeConfigEntry:
        entry_id: str = "entry_123"
        title: str = "Kano-Wand-75"
        data: dict[str, Any] = field(
            default_factory=lambda: {"address": "AA:BB:CC:DD:EE:FF"}
        )
        _unload_callbacks: list[Callable] = field(default_factory=list)
        background_tasks: list[asyncio.Task] = field(default_factory=list)

        def async_on_unload(self, fn: Callable) -> None:
            self._unload_callbacks.append(fn)

        def async_create_background_task(
            self, hass: Any, coro: Any, name: str
        ) -> asyncio.Task:
            task = asyncio.create_task(coro, name=name)
            self.background_tasks.append(task)
            return task

    ce.ConfigEntry = FakeConfigEntry
    sys.modules["homeassistant.config_entries"] = ce

    # homeassistant.components.bluetooth
    bt = types.ModuleType("homeassistant.components.bluetooth")

    @dataclass
    class BluetoothServiceInfoBleak:
        name: str
        address: str
        rssi: int
        manufacturer_data: dict[int, bytes]
        service_data: dict[str, bytes]
        service_uuids: list[str]
        source: str
        device: Any
        advertisement: Any

    class BluetoothScanningMode:
        ACTIVE = "active"

    class BluetoothChange:
        ADVERTISEMENT = "advertisement"

    bt.BluetoothServiceInfoBleak = BluetoothServiceInfoBleak
    bt.BluetoothScanningMode = BluetoothScanningMode
    bt.BluetoothChange = BluetoothChange
    bt.async_ble_device_from_address = (
        lambda hass, address, connectable=True: hass.ble_device
    )

    def _reg_cb(hass: Any, cb: Callable, matcher: Any, mode: Any) -> Callable:
        hass.ble_callbacks.append(cb)
        return lambda: hass.ble_callbacks.remove(cb)

    bt.async_register_callback = _reg_cb
    bt.async_discovered_service_info = lambda hass, connectable=True: []
    sys.modules["homeassistant.components"] = types.ModuleType(
        "homeassistant.components"
    )
    sys.modules["homeassistant.components"].bluetooth = bt
    sys.modules["homeassistant.components.bluetooth"] = bt

    bt_match = types.ModuleType("homeassistant.components.bluetooth.match")
    bt_match.ADDRESS = "address"
    bt_match.BluetoothCallbackMatcher = dict
    sys.modules["homeassistant.components.bluetooth.match"] = bt_match

    # homeassistant.helpers
    helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers

    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.ensure_list = lambda x: x if isinstance(x, list) else [x]
    cv.string = str
    helpers.config_validation = cv
    sys.modules["homeassistant.helpers.config_validation"] = cv

    dr = types.ModuleType("homeassistant.helpers.device_registry")
    dr.CONNECTION_BLUETOOTH = "bluetooth"
    dr.DeviceInfo = dict
    dr.async_get = lambda hass: MagicMock()
    helpers.device_registry = dr
    sys.modules["homeassistant.helpers.device_registry"] = dr

    er = types.ModuleType("homeassistant.helpers.entity_registry")
    er.async_get = lambda hass: getattr(hass, "_entity_registry", MagicMock(async_get_entity_id=MagicMock(return_value=None)))
    helpers.entity_registry = er
    sys.modules["homeassistant.helpers.entity_registry"] = er

    rs = types.ModuleType("homeassistant.helpers.restore_state")

    class RestoreEntity:
        async def async_get_last_state(self) -> Any:
            return None

    rs.RestoreEntity = RestoreEntity
    helpers.restore_state = rs
    sys.modules["homeassistant.helpers.restore_state"] = rs

    disp = types.ModuleType("homeassistant.helpers.dispatcher")

    def _disp_send(hass: Any, signal: str, *args: Any) -> None:
        for cb in list(hass.dispatcher.get(signal, [])):
            cb(*args)

    def _disp_conn(hass: Any, signal: str, cb: Callable) -> Callable:
        hass.dispatcher.setdefault(signal, []).append(cb)
        return lambda: hass.dispatcher[signal].remove(cb)

    disp.async_dispatcher_send = _disp_send
    disp.async_dispatcher_connect = _disp_conn
    sys.modules["homeassistant.helpers.dispatcher"] = disp

    ent_mod = types.ModuleType("homeassistant.helpers.entity")

    class Entity:
        hass: Any = None

        def __init__(self) -> None:
            self._unsubs: list[Callable] = []

        @property
        def unique_id(self) -> str:
            return getattr(self, "_attr_unique_id", "")

        def async_on_remove(self, fn: Callable) -> None:
            self._unsubs.append(fn)

        async def async_added_to_hass(self) -> None:
            pass

        def async_write_ha_state(self) -> None:
            pass

    ent_mod.Entity = Entity
    ent_mod.DeviceInfo = dict
    sys.modules["homeassistant.helpers.entity"] = ent_mod

    ep_mod = types.ModuleType("homeassistant.helpers.entity_platform")
    ep_mod.AddEntitiesCallback = Callable
    sys.modules["homeassistant.helpers.entity_platform"] = ep_mod

    # Platform entity base classes
    sensor_mod = types.ModuleType("homeassistant.components.sensor")
    sensor_mod.SensorEntity = Entity
    sensor_mod.SensorDeviceClass = types.SimpleNamespace(BATTERY="battery")
    sensor_mod.SensorStateClass = types.SimpleNamespace(MEASUREMENT="measurement")
    sys.modules["homeassistant.components.sensor"] = sensor_mod

    bs_mod = types.ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorEntity(Entity):
        @property
        def is_on(self) -> bool | None:
            return getattr(self, "_attr_is_on", None)

    bs_mod.BinarySensorEntity = BinarySensorEntity
    bs_mod.BinarySensorDeviceClass = types.SimpleNamespace(
        CONNECTIVITY="connectivity", POWER="power"
    )
    sys.modules["homeassistant.components.binary_sensor"] = bs_mod

    ev_mod = types.ModuleType("homeassistant.components.event")

    class EventEntity(Entity):
        def __init__(self) -> None:
            super().__init__()
            self.last_event_type: str | None = None
            self.last_event_attributes: dict[str, Any] = {}

        @property
        def event_types(self) -> list[str]:
            return getattr(self, "_attr_event_types", [])

        def _trigger_event(
            self, event_type: str, event_attributes: dict[str, Any] | None = None
        ) -> None:
            self.last_event_type = event_type
            self.last_event_attributes = event_attributes or {}

    ev_mod.EventEntity = EventEntity
    sys.modules["homeassistant.components.event"] = ev_mod

    light_mod = types.ModuleType("homeassistant.components.light")
    light_mod.ATTR_RGB_COLOR = "rgb_color"
    light_mod.ColorMode = types.SimpleNamespace(RGB="rgb")

    class LightEntity(Entity):
        @property
        def is_on(self) -> bool | None:
            return getattr(self, "_attr_is_on", None)

        @property
        def rgb_color(self) -> tuple[int, int, int] | None:
            return getattr(self, "_attr_rgb_color", None)

    light_mod.LightEntity = LightEntity
    sys.modules["homeassistant.components.light"] = light_mod

    num_mod = types.ModuleType("homeassistant.components.number")
    num_mod.NumberMode = types.SimpleNamespace(SLIDER="slider")

    class RestoreNumber(Entity):
        @property
        def native_value(self) -> float | None:
            return getattr(self, "_attr_native_value", None)

        async def async_get_last_number_data(self) -> Any:
            return None

    num_mod.RestoreNumber = RestoreNumber
    sys.modules["homeassistant.components.number"] = num_mod

    btn_mod = types.ModuleType("homeassistant.components.button")
    btn_mod.ButtonEntity = Entity
    sys.modules["homeassistant.components.button"] = btn_mod

    img_mod = types.ModuleType("homeassistant.components.image")

    class ImageEntity(Entity):
        def __init__(self, hass: Any) -> None:
            super().__init__()
            self.hass = hass

    img_mod.ImageEntity = ImageEntity
    sys.modules["homeassistant.components.image"] = img_mod

    sw_mod = types.ModuleType("homeassistant.components.switch")

    class SwitchEntity(Entity):
        @property
        def is_on(self) -> bool | None:
            return getattr(self, "_attr_is_on", None)

    sw_mod.SwitchEntity = SwitchEntity
    sys.modules["homeassistant.components.switch"] = sw_mod

    sel_mod = types.ModuleType("homeassistant.components.select")

    class SelectEntity(Entity):
        @property
        def current_option(self) -> str | None:
            return getattr(self, "_attr_current_option", None)

        @property
        def options(self) -> list[str]:
            return getattr(self, "_attr_options", [])

    sel_mod.SelectEntity = SelectEntity
    sys.modules["homeassistant.components.select"] = sel_mod

    util_mod = types.ModuleType("homeassistant.util")
    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.utcnow = lambda: datetime.datetime.now(datetime.timezone.utc)
    util_mod.dt = dt_mod
    sys.modules["homeassistant.util"] = util_mod
    sys.modules["homeassistant.util.dt"] = dt_mod


_install_ha_stubs()


@pytest.fixture(scope="session")
def gesture_spells():
    """Shared GestureSpells TFLite instance across test session."""
    from custom_components.kano_wand.gesture import GestureSpells

    return GestureSpells(load_immediately=True)


@pytest.fixture
def hass():
    """Create a fresh FakeHomeAssistant instance for each test."""
    from homeassistant.core import HomeAssistant

    return HomeAssistant()


@pytest.fixture
def config_entry():
    """Create a fresh FakeConfigEntry instance for each test."""
    from homeassistant.config_entries import ConfigEntry

    return ConfigEntry()


@pytest.fixture
def fake_ble_client():
    """Create a mocked BleakClient with battery read support."""
    from custom_components.kano_wand.const import CHAR_BATTERY

    client = MagicMock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.write_gatt_char = AsyncMock()
    client.read_gatt_char = AsyncMock(
        side_effect=lambda uuid: bytearray([87]) if uuid == CHAR_BATTERY else b"1.2.3"
    )
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def fake_ble_device():
    """Create a mocked BLEDevice."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "Kano-Wand-75"
    return device
