"""End-to-end local test suite for the Kano Wand Home Assistant custom component.

Runs on Windows/macOS/Linux without requiring Unix-only Home Assistant Core dependencies.
Run with:
  uv run python tests/test_ha_integration.py
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import sys
import types
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _install_ha_stubs() -> None:
    """Install lightweight Home Assistant stubs for Windows local testing."""
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
        unique_id: str = ""

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
        def __init__(self, hass: Any = None) -> None:
            super().__init__()
            self.hass = hass

    img_mod.ImageEntity = ImageEntity
    sys.modules["homeassistant.components.image"] = img_mod

    util_mod = types.ModuleType("homeassistant.util")
    dt_mod = types.ModuleType("homeassistant.util.dt")
    import datetime
    dt_mod.utcnow = lambda: datetime.datetime.now(datetime.timezone.utc)
    util_mod.dt = dt_mod
    sys.modules["homeassistant.util"] = util_mod
    sys.modules["homeassistant.util.dt"] = dt_mod


async def run_integration_tests() -> None:
    """Run full Home Assistant integration lifecycle and entity tests."""
    _install_ha_stubs()

    from homeassistant.components.bluetooth import (
        BluetoothChange,
        BluetoothServiceInfoBleak,
    )
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from custom_components.kano_wand import async_setup_entry, async_unload_entry
    from custom_components.kano_wand.const import (
        CHAR_BATTERY,
        CHAR_LED,
        CHAR_VIBRATOR,
        DOMAIN,
        SERVICE_VIBRATE,
    )

    print("=== Testing Home Assistant Kano Wand Integration ===")
    hass = HomeAssistant()
    entry = ConfigEntry()

    # 1. Setup entry while wand is asleep (ble_device is None) -> should succeed!
    setup_ok = await async_setup_entry(hass, entry)
    assert setup_ok is True, "async_setup_entry should succeed even when wand is asleep"
    print("[PASS] async_setup_entry succeeded while wand is asleep")

    # Verify all 9 entities across 7 platforms were created
    expected_ids = {
        "entry_123_last_spell",
        "entry_123_battery",
        "entry_123_button",
        "entry_123_connected",
        "entry_123_spell_event",
        "entry_123_led",
        "entry_123_keep_alive_timeout",
        "entry_123_vibrate",
        "entry_123_last_spell_drawing",
    }
    assert set(hass.entities.keys()) == expected_ids
    print(f"[PASS] Registered all {len(expected_ids)} entities across 7 platforms")

    # 2. Simulate Bluetooth proxy advertisement waking up the wand in another room
    fake_ble_client = MagicMock()
    fake_ble_client.is_connected = True
    fake_ble_client.start_notify = AsyncMock()
    fake_ble_client.write_gatt_char = AsyncMock()
    fake_ble_client.read_gatt_char = AsyncMock(
        side_effect=lambda uuid: bytearray([87]) if uuid == CHAR_BATTERY else b"1.2.3"
    )
    fake_ble_client.disconnect = AsyncMock()

    fake_ble_device = MagicMock()
    fake_ble_device.address = "AA:BB:CC:DD:EE:FF"
    fake_ble_device.name = "Kano-Wand-75"
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

        await asyncio.gather(*entry.background_tasks)
        wand = hass.data[DOMAIN][entry.entry_id]
        if wand._background_tasks:
            await asyncio.gather(*list(wand._background_tasks))

        assert mock_establish.await_count == 1
        assert hass.entities["entry_123_connected"].is_on is True
        assert hass.entities["entry_123_battery"].native_value == 87
        vibrate_calls = [
            c for c in fake_ble_client.write_gatt_char.call_args_list
            if c.args[0] == CHAR_VIBRATOR and c.args[1] == bytearray([3])
        ]
        assert len(vibrate_calls) == 1
        print("[PASS] Automatic proxy connection, burst welcome vibrate, & battery read (87%)")

    # 3. Test dynamic Keep-Alive Timeout slider entity
    timeout_entity = hass.entities["entry_123_keep_alive_timeout"]
    await timeout_entity.async_set_native_value(5.5)
    wand = hass.data[DOMAIN][entry.entry_id]
    assert wand.keep_alive_timeout_minutes == 5.5
    print("[PASS] Keep Alive Timeout number slider dynamically updated wand timeout to 5.5 min")

    # 4. Test RGB LED Light entity
    led_entity = hass.entities["entry_123_led"]
    await led_entity.async_turn_on(rgb_color=(255, 0, 128))
    assert led_entity.is_on is True
    assert led_entity.rgb_color == (255, 0, 128)
    fake_ble_client.write_gatt_char.assert_any_call(
        CHAR_LED, bytearray([1, 248, 16]), True
    )
    await led_entity.async_turn_off()
    assert led_entity.is_on is False
    print("[PASS] RGB LED LightEntity turn_on (RGB565 encoding) and turn_off")

    # 5. Test Vibrate Button entity and kano_wand.vibrate Service
    vibrate_btn = hass.entities["entry_123_vibrate"]
    await vibrate_btn.async_press()
    fake_ble_client.write_gatt_char.assert_any_call(
        CHAR_VIBRATOR, bytearray([1]), True
    )
    await hass.services.async_call(DOMAIN, SERVICE_VIBRATE, {"pattern": "burst"})
    fake_ble_client.write_gatt_char.assert_any_call(
        CHAR_VIBRATOR, bytearray([3]), True
    )
    print("[PASS] Vibrate ButtonEntity and kano_wand.vibrate action ('burst' -> pattern 3)")

    # 6. Test casting the SAME spell twice in a row -> EventEntity, ImageEntity, & Event Bus fire
    spell_sensor = hass.entities["entry_123_last_spell"]
    spell_event = hass.entities["entry_123_spell_event"]
    spell_image = hass.entities["entry_123_last_spell_drawing"]
    button_sensor = hass.entities["entry_123_button"]

    wand._on_button_notification(None, bytearray([1]))
    assert button_sensor.is_on is True
    lumos_points = [[300 + i * 5, 500 - i * 15] for i in range(15)] + [
        [375 + i * 5, 275 + i * 15] for i in range(15)
    ]
    wand._on_spell_cb_data = {
        "spell": "Lumos",
        "score": 0.96,
        "duration": 0.85,
        "points": len(lumos_points),
        "positions": lumos_points,
    }
    wand.on_spell_cb(wand._on_spell_cb_data)
    assert spell_event.last_event_type == "Lumos"
    png_bytes = await spell_image.async_image()
    assert png_bytes is not None and png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    wand.on_spell_cb(wand._on_spell_cb_data)
    assert spell_event.last_event_type == "Lumos"
    wand._on_button_notification(None, bytearray([0]))
    assert button_sensor.is_on is False
    # Short click (<0.2s) emits "recentre" on EventEntity, while Last Spell sensor & Image keep "Lumos"
    assert spell_event.last_event_type == "recentre"
    assert spell_sensor.native_value == "Lumos"
    assert spell_sensor.extra_state_attributes["score"] == 0.96
    assert spell_image.extra_state_attributes["spell"] == "Lumos"
    lumos_bus_events = [
        e for e in hass.bus.events if e[1].get("spell") == "Lumos"
    ]
    assert len(lumos_bus_events) == 2
    print("[PASS] Spell Sensor, Spell EventEntity, and HA Event Bus fired on repeated casts")

    # 7. Test unexpected BLE disconnect & clean unload
    wand._on_disconnected(fake_ble_client)
    assert hass.entities["entry_123_connected"].is_on is False
    assert hass.entities["entry_123_led"].is_on is False
    print("[PASS] BLE disconnected callback updated entity states cleanly")

    unload_ok = await async_unload_entry(hass, entry)
    assert unload_ok is True
    assert entry.entry_id not in hass.data[DOMAIN]
    print("[PASS] async_unload_entry cleaned up resources and services")
    print("=== All Home Assistant Integration Tests Passed! ===")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
