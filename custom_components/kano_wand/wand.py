"""Kano Wand BLE client for Home Assistant and standalone testing."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import (
    CHAR_BATTERY,
    CHAR_BUTTON,
    CHAR_HARDWARE,
    CHAR_KEEP_ALIVE,
    CHAR_LED,
    CHAR_MAGN_CALIBRATE,
    CHAR_ORGANIZATION,
    CHAR_QUATERNIONS,
    CHAR_QUATERNIONS_RESET,
    CHAR_SOFTWARE,
    CHAR_TEMP,
    CHAR_VIBRATOR,
    DEFAULT_KEEP_ALIVE_TIMEOUT_MINUTES,
    EVENT_TYPE_RECENTRE,
    KEEP_ALIVE_INTERVAL_SECONDS,
    NOT_A_SPELL,
    VIBRATION_BURST,
    VIBRATION_PATTERNS,
    VIBRATION_REGULAR,
    VIBRATION_SHORT,
)
from .conversion import WandConversion
from .gesture import GestureSpells

_LOGGER = logging.getLogger(__name__)

# Virtual canvas dimensions for quaternion-to-2D projection
WIDTH = 800
HEIGHT = 600


class FlickDetector:
    """Directional flick gesture detector ported from the official Kano Wand app (editor.js)."""

    def __init__(
        self,
        width: int = WIDTH,
        height: int = HEIGHT,
        cooldown_seconds: float = 0.45,
    ) -> None:
        """Initialize the flick detector."""
        self.width = width
        self.height = height
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger_time: float = 0.0
        self.strength_x = 100.0
        self.strength_y = 80.0
        self.strength_sq_x = self.strength_x**2
        self.strength_sq_y = self.strength_y**2
        self.reset()

    def reset(self) -> None:
        """Reset flick state (e.g. while button is held for spell drawing)."""
        self._last_point: tuple[float, float] = (self.width / 2.0, self.height / 2.0)
        self.prev_point: tuple[float, float] | None = None
        self.vertical: bool | None = None
        self.direction: str | None = None
        self.wand_gesture: list[float] = []

    def process_point(
        self, x: float, y: float, now: float | None = None
    ) -> dict[str, Any] | None:
        """Process a 2D projected point and return a flick event dict if completed."""
        ts = now if now is not None else time.monotonic()
        speed = WandConversion.distance(self._last_point[0], x, self._last_point[1], y) / 0.4
        self._last_point = (x, y)

        if self.prev_point is not None:
            if x < -200 or x > 1000:
                self.prev_point = self._last_point
                return None

            dx = x - self.prev_point[0]
            dy = y - self.prev_point[1]
            sx = dx * dx
            sy = dy * dy

            if len(self.wand_gesture) >= 2:
                is_vert = sy > sx
                delta = dy if is_vert else dx
                strong_enough = (delta * delta) > self.strength_sq_x
                if is_vert == self.vertical and speed > 10.0 and strong_enough:
                    self.wand_gesture.append(delta)
                    return None

                direction = self.direction
                intensity = round(max((abs(v) for v in self.wand_gesture), default=0.0), 1)
                self.wand_gesture.clear()
                self.vertical = None
                self.direction = None
                self.prev_point = self._last_point
                if direction and (ts - self._last_trigger_time) >= self.cooldown_seconds:
                    self._last_trigger_time = ts
                    return {"direction": direction, "intensity": intensity}
                return None

            if sx > sy and sx > self.strength_sq_x:
                self.wand_gesture.append(dx)
                self.vertical = False
                self.direction = "right" if dx > 0 else "left"
                return None
            if sy > sx and sy > self.strength_sq_y:
                self.wand_gesture.append(dy)
                self.vertical = True
                self.direction = "down" if dy > 0 else "up"
                return None

        self.prev_point = self._last_point
        return None


class KanoWand:
    """Interface to a Kano Wand BLE device with proxy-friendly reconnection."""

    def __init__(
        self,
        ble_device_callback: Callable[[], BLEDevice | None],
        name: str = "Kano Wand",
        on_button: Callable[[bool], None] | None = None,
        on_spell: Callable[[dict[str, Any]], None] | None = None,
        on_draw: Callable[[dict[str, Any]], None] | None = None,
        on_flick: Callable[[dict[str, Any]], None] | None = None,
        on_connected: Callable[[bool], None] | None = None,
        on_led: Callable[[bool, tuple[int, int, int]], None] | None = None,
        on_battery: Callable[[bool], None] | None = None,
        on_temperature: Callable[[float], None] | None = None,
        on_device_info: Callable[[str | None, str | None], None] | None = None,
        gesture_spells: GestureSpells | None = None,
        vibrate_on_connect: bool = True,
    ) -> None:
        """Initialize the wand manager."""
        self._ble_device_callback = ble_device_callback
        self.name = name
        self.on_button_cb = on_button
        self.on_spell_cb = on_spell
        self.on_draw_cb = on_draw
        self.on_flick_cb = on_flick
        self.on_connected_cb = on_connected
        self.on_led_cb = on_led
        self.on_battery_cb = on_battery
        self.on_temperature_cb = on_temperature
        self.on_device_info_cb = on_device_info
        self.vibrate_on_connect = vibrate_on_connect
        self.vibrate_on_spell: bool = True
        self.vibration_pattern: str = "regular"
        self.min_spell_confidence: float = 0.0

        self.client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._expected_disconnect = False
        self._is_connected = False
        self.auto_connect: bool = True

        self.conversion = WandConversion(WIDTH, HEIGHT)
        self.flick_detector = FlickDetector(WIDTH, HEIGHT)
        self.gs = gesture_spells or GestureSpells(load_immediately=True)

        # Runtime state
        self.button_pressed: bool = False
        self.current_spell: list[list[float]] = []
        self._time_button_down: float = 0.0
        self._time_button_up: float = 0.0
        # Matches official Kano Wand app 350ms pressTimeout between short click (recentre) and spell draw
        self.reset_timeout: float = 0.35

        # Keep-alive & activity tracking
        self.keep_alive_timeout_minutes: float = DEFAULT_KEEP_ALIVE_TIMEOUT_MINUTES
        self._last_activity: float = time.monotonic()
        self.keep_alive_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # LED, Battery, Temperature & Device Info state
        self.led_on: bool = False
        self.led_rgb: tuple[int, int, int] = (148, 0, 211)  # Default magic purple
        self.battery_low: bool = False
        self.temperature: float | None = None
        self.hardware_version: str | None = None
        self.software_version: str | None = None
        self.organization: str | None = None

        # Telemetry counters (in-memory only, for diagnostics & live BLE testing)
        self.quaternion_packets_received: int = 0
        self._rate_window_start: float = time.monotonic()
        self._rate_window_count: int = 0
        self.quaternion_rate_hz: float = 0.0

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to the wand."""
        return (
            self._is_connected
            and self.client is not None
            and self.client.is_connected
        )

    @property
    def is_connecting(self) -> bool:
        """Return True if a connection attempt is currently in progress."""
        return self._connect_lock.locked()

    def _spawn_background_task(
        self, coro: Any, name: str
    ) -> asyncio.Task[Any]:
        """Create and track a background task."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def set_keep_alive_timeout(self, minutes: float) -> None:
        """Update the idle keep-alive timeout in minutes."""
        self.keep_alive_timeout_minutes = max(0.0, float(minutes))
        self._record_activity()
        _LOGGER.debug(
            "%s: Keep-alive timeout set to %.1f minutes",
            self.name,
            self.keep_alive_timeout_minutes,
        )

    def _record_activity(self) -> None:
        """Record user or automation interaction with the wand."""
        self._last_activity = time.monotonic()

    async def ensure_connected(self, ble_device: BLEDevice | None = None) -> bool:
        """Connect to the wand if not already connected."""
        if not self.auto_connect:
            _LOGGER.debug("%s: Auto-connect is disabled; skipping connection", self.name)
            return False

        if self.is_connected:
            return True

        if self._connect_lock.locked():
            return False

        async with self._connect_lock:
            if self.is_connected:
                return True

            device = ble_device or self._ble_device_callback()
            if device is None:
                _LOGGER.debug("%s: No connectable BLEDevice currently available", self.name)
                return False

            t_start = time.perf_counter()
            _LOGGER.info(
                "Connecting to Kano Wand %s (%s)",
                self.name,
                device.address,
            )
            self._expected_disconnect = False

            try:
                self.client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    self.name,
                    self._on_disconnected,
                    use_services_cache=True,
                    ble_device_callback=lambda: self._ble_device_callback() or device,
                )
            except (BleakError, TimeoutError, OSError) as ex:
                _LOGGER.debug("Failed to connect to %s: %s", self.name, ex)
                self.client = None
                if self.on_connected_cb:
                    self.on_connected_cb(False)
                return False
            except Exception as ex:
                _LOGGER.warning("Unexpected error connecting to %s: %s", self.name, ex)
                self.client = None
                if self.on_connected_cb:
                    self.on_connected_cb(False)
                return False

            try:
                await self._setup_subscriptions()
            except Exception as ex:
                _LOGGER.warning(
                    "Connected to %s but failed to initialize GATT subscriptions: %s",
                    self.name,
                    ex,
                )
                await self.disconnect()
                return False

            self._is_connected = True
            self._record_activity()
            if self.keep_alive_task is None or self.keep_alive_task.done():
                self.keep_alive_task = asyncio.create_task(
                    self._keep_alive_loop(), name=f"{self.name}_keep_alive"
                )

            dt = time.perf_counter() - t_start
            _LOGGER.info(
                "Kano Wand %s (%s) connected and ready in %.2fs",
                self.name,
                device.address,
                dt,
            )
            if self.on_connected_cb:
                self.on_connected_cb(True)

            # Vibrate 3 times & fetch static device metadata in the background
            self._spawn_background_task(
                self._post_connect_tasks(),
                f"{self.name}_post_connect",
            )
            return True

    async def _setup_subscriptions(self) -> None:
        """Subscribe to essential notifications with minimal GATT round-trips."""
        assert self.client is not None

        await self.client.start_notify(CHAR_BUTTON, self._on_button_notification)
        await self.client.start_notify(CHAR_QUATERNIONS, self._on_motion_notification)
        await self.reset_position()

    async def _post_connect_tasks(self) -> None:
        """Run non-blocking welcome vibration (hardware burst), LED indicator, and metadata read."""
        try:
            if self.vibrate_on_connect and self.is_connected:
                await self.set_led(True, self.led_rgb)
                await self.vibrate(VIBRATION_BURST)

            if self.client and self.is_connected:
                with contextlib.suppress(Exception):
                    batt_raw = await self.client.read_gatt_char(CHAR_BATTERY)
                    if isinstance(batt_raw, (bytes, bytearray)) and len(batt_raw) == 1:
                        self._on_battery_notification(None, bytearray(batt_raw))
                with contextlib.suppress(Exception):
                    await self.client.start_notify(
                        CHAR_BATTERY, self._on_battery_notification
                    )
                with contextlib.suppress(Exception):
                    temp_raw = await self.client.read_gatt_char(CHAR_TEMP)
                    if isinstance(temp_raw, (bytes, bytearray)) and len(temp_raw) == 2:
                        self._on_temperature_notification(None, bytearray(temp_raw))
                with contextlib.suppress(Exception):
                    await self.client.start_notify(
                        CHAR_TEMP, self._on_temperature_notification
                    )

            if self.software_version is None and self.client and self.is_connected:
                with contextlib.suppress(Exception):
                    sw = await self.client.read_gatt_char(CHAR_SOFTWARE)
                    self.software_version = sw.decode("utf-8", errors="ignore").strip("\x00 ")
                with contextlib.suppress(Exception):
                    hw = await self.client.read_gatt_char(CHAR_HARDWARE)
                    self.hardware_version = hw.decode("utf-8", errors="ignore").strip("\x00 ")
                with contextlib.suppress(Exception):
                    org = await self.client.read_gatt_char(CHAR_ORGANIZATION)
                    self.organization = org.decode("utf-8", errors="ignore").strip("\x00 ")
                if self.on_device_info_cb:
                    self.on_device_info_cb(self.software_version, self.hardware_version)
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            _LOGGER.debug("%s: Post-connect task error: %s", self.name, ex)

    def _on_disconnected(self, client: BleakClient) -> None:
        """Handle BLE disconnection callback from Bleak."""
        was_connected = self._is_connected
        self._is_connected = False
        self.client = None
        self.button_pressed = False
        self.current_spell.clear()

        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel()
        self.keep_alive_task = None

        if was_connected:
            _LOGGER.info(
                "Kano Wand %s disconnected (expected=%s)",
                self.name,
                self._expected_disconnect,
            )
            if self.on_button_cb:
                self.on_button_cb(False)
            if self.on_connected_cb:
                self.on_connected_cb(False)

    async def disconnect(self) -> None:
        """Disconnect from the wand and clean up background tasks."""
        self._expected_disconnect = True
        was_connected = self._is_connected
        self._is_connected = False

        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.keep_alive_task
        self.keep_alive_task = None

        for task in list(self._background_tasks):
            task.cancel()

        client = self.client
        self.client = None
        if client and client.is_connected:
            with contextlib.suppress(Exception):
                await client.disconnect()

        if was_connected and self.on_connected_cb:
            self.on_connected_cb(False)

    async def _keep_alive_loop(self) -> None:
        """Send keep-alive packets while within the active idle timeout window."""
        try:
            while self.is_connected:
                timeout_seconds = self.keep_alive_timeout_minutes * 60.0
                idle_seconds = time.monotonic() - self._last_activity

                if timeout_seconds > 0 and idle_seconds < timeout_seconds:
                    await self.keep_alive()
                elif timeout_seconds > 0 and idle_seconds >= timeout_seconds:
                    _LOGGER.debug(
                        "%s: Idle for %.0fs (timeout %.0fs); pausing keep-alive so wand can sleep",
                        self.name,
                        idle_seconds,
                        timeout_seconds,
                    )
                await asyncio.sleep(KEEP_ALIVE_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            _LOGGER.debug("%s: Keep-alive loop exited: %s", self.name, ex)

    async def keep_alive(self) -> None:
        """Send a single keep-alive ping to prevent the wand from sleeping."""
        if not self.is_connected or self.client is None:
            return
        with contextlib.suppress(BleakError, OSError):
            await self.client.write_gatt_char(CHAR_KEEP_ALIVE, bytearray([1]), True)

    async def reset_position(self) -> None:
        """Reset the wand's internal quaternion orientation."""
        if not self.client or not self.client.is_connected:
            return
        with contextlib.suppress(BleakError, OSError):
            await self.client.write_gatt_char(
                CHAR_QUATERNIONS_RESET, bytearray([1]), True
            )

    async def calibrate_magnetometer(self) -> bool:
        """Run hardware magnetometer calibration on the wand's IMU (matching official Kano app)."""
        self._record_activity()
        if not self.is_connected:
            if not await self.ensure_connected():
                raise BleakError(f"{self.name} is not connected")

        assert self.client is not None
        done_event = asyncio.Event()
        result_status: list[int] = []

        def _on_cal_notify(sender: Any, data: bytearray) -> None:
            if data and data[0] in (2, 3):
                result_status.append(data[0])
                done_event.set()

        with contextlib.suppress(Exception):
            await self.client.stop_notify(CHAR_QUATERNIONS)

        try:
            await self.client.start_notify(CHAR_MAGN_CALIBRATE, _on_cal_notify)
            await self.client.write_gatt_char(
                CHAR_MAGN_CALIBRATE, bytearray([1]), True
            )
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(done_event.wait(), timeout=3.0)
        finally:
            if self.client and self.client.is_connected:
                with contextlib.suppress(Exception):
                    await self.client.stop_notify(CHAR_MAGN_CALIBRATE)
                with contextlib.suppress(Exception):
                    await self.client.start_notify(
                        CHAR_QUATERNIONS, self._on_motion_notification
                    )

        return not result_status or result_status[-1] == 2

    async def vibrate(self, pattern: int | str = VIBRATION_REGULAR) -> None:
        """Make the wand vibrate using a pattern name or integer (1-7)."""
        self._record_activity()
        if isinstance(pattern, str):
            pattern_int = VIBRATION_PATTERNS.get(pattern.lower(), VIBRATION_REGULAR)
        else:
            pattern_int = max(1, min(7, int(pattern)))

        if not self.is_connected:
            if not await self.ensure_connected():
                raise BleakError(f"{self.name} is not connected")

        assert self.client is not None
        await self.client.write_gatt_char(
            CHAR_VIBRATOR, bytearray([pattern_int]), True
        )

    async def set_led(
        self, state: bool, rgb: tuple[int, int, int] | None = None
    ) -> None:
        """Control the RGB LED on the wand tip (encoded as RGB565)."""
        self._record_activity()
        if rgb is not None:
            self.led_rgb = (
                max(0, min(255, int(rgb[0]))),
                max(0, min(255, int(rgb[1]))),
                max(0, min(255, int(rgb[2]))),
            )
        self.led_on = bool(state)

        if not self.is_connected:
            if not await self.ensure_connected():
                raise BleakError(f"{self.name} is not connected")

        r, g, b = self.led_rgb if self.led_on else (0, 0, 0)
        rgb565 = ((r & 248) << 8) + ((g & 252) << 3) + ((b & 248) >> 3)
        message = bytearray([1 if self.led_on else 0, (rgb565 >> 8) & 0xFF, rgb565 & 0xFF])

        assert self.client is not None
        await self.client.write_gatt_char(CHAR_LED, message, True)

        if self.on_led_cb:
            self.on_led_cb(self.led_on, self.led_rgb)

    def _on_button_notification(self, sender: Any, data: bytearray) -> None:
        """Handle button press/release GATT notifications."""
        if not data:
            return
        self._record_activity()
        pressed = data[0] == 1
        self.button_pressed = pressed

        if pressed:
            self._time_button_down = time.monotonic()
            self.current_spell.clear()
            self.flick_detector.reset()
        else:
            self._time_button_up = time.monotonic()
            seconds = self._time_button_up - self._time_button_down
            self.flick_detector.reset()

            if seconds < self.reset_timeout:
                # Short click: recentre orientation and emit recentre event
                self._spawn_background_task(
                    self._async_recentre_and_keep_alive(),
                    f"{self.name}_recentre",
                )
                if self.on_spell_cb:
                    self.on_spell_cb(
                        {
                            "spell": EVENT_TYPE_RECENTRE,
                            "score": 1.0,
                            "duration": round(seconds, 3),
                            "points": 0,
                        }
                    )
            elif len(self.current_spell) > 5:
                # At 25 Hz (40ms/sample), trim 2 leading samples (button press) and
                # 1 trailing sample (button release thumb lift) to prevent endpoint hooks.
                if len(self.current_spell) > 7:
                    raw_points = self.current_spell[2:-1]
                else:
                    raw_points = list(self.current_spell)
                flipped_positions = [self._flip_cord(entry) for entry in raw_points]
                try:
                    cleaned_positions = self.gs.clean_trajectory(flipped_positions)
                    spell_data = self.gs.recognise(cleaned_positions)
                    spell_name = spell_data.get("spell")
                    score_pct = float(spell_data.get("score") or 0.0) * 100.0
                    spell_data["duration"] = round(seconds, 3)
                    spell_data["points"] = len(cleaned_positions)
                    spell_data["positions"] = cleaned_positions

                    if spell_name == NOT_A_SPELL:
                        spell_data["recognized"] = False
                        spell_data["status"] = "unrecognized"
                        _LOGGER.debug(
                            "%s: Gesture classified as non-spell (closest: %s %.1f%%)",
                            self.name,
                            spell_data.get("closest_spell"),
                            float(spell_data.get("closest_score") or 0.0) * 100.0,
                        )
                        if self.on_draw_cb:
                            self.on_draw_cb(spell_data)
                    elif score_pct >= self.min_spell_confidence:
                        spell_data["recognized"] = True
                        spell_data["status"] = "recognized"
                        if self.vibrate_on_spell and self.is_connected:
                            self._spawn_background_task(
                                self.vibrate(VIBRATION_SHORT),
                                f"{self.name}_spell_vibrate",
                            )
                        if self.on_draw_cb:
                            self.on_draw_cb(spell_data)
                        if self.on_spell_cb:
                            self.on_spell_cb(spell_data)
                    else:
                        spell_data["recognized"] = False
                        spell_data["status"] = "low_confidence"
                        _LOGGER.debug(
                            "%s: Ignoring spell %s (confidence %.1f%% < minimum %.1f%%)",
                            self.name,
                            spell_name,
                            score_pct,
                            self.min_spell_confidence,
                        )
                        if self.on_draw_cb:
                            self.on_draw_cb(spell_data)
                except Exception as ex:
                    _LOGGER.warning("Error recognizing spell gesture: %s", ex)
            elif len(self.current_spell) >= 2:
                flipped_positions = [
                    self._flip_cord(entry) for entry in self.current_spell
                ]
                if self.on_draw_cb:
                    self.on_draw_cb(
                        {
                            "spell": NOT_A_SPELL,
                            "recognized": False,
                            "status": "too_short",
                            "score": 0.0,
                            "closest_spell": None,
                            "closest_score": 0.0,
                            "duration": round(seconds, 3),
                            "points": len(flipped_positions),
                            "positions": flipped_positions,
                        }
                    )

            self.current_spell.clear()

        if self.on_button_cb:
            self.on_button_cb(pressed)

    async def _async_recentre_and_keep_alive(self) -> None:
        """Reset orientation and send keep-alive on short button click."""
        await self.reset_position()
        await self.keep_alive()

    def _on_motion_notification(self, sender: Any, data: bytearray) -> None:
        """Handle high-frequency (~50Hz) quaternion motion notifications in memory."""
        self.quaternion_packets_received += 1
        self._rate_window_count += 1
        now = time.monotonic()
        elapsed = now - self._rate_window_start
        if elapsed >= 1.0:
            self.quaternion_rate_hz = round(self._rate_window_count / elapsed, 1)
            self._rate_window_start = now
            self._rate_window_count = 0

        if len(data) < 8:
            return

        y = int.from_bytes(data[0:2], byteorder="little", signed=True)
        x = int.from_bytes(data[2:4], byteorder="little", signed=True)
        w = int.from_bytes(data[4:6], byteorder="little", signed=True)
        z = int.from_bytes(data[6:8], byteorder="little", signed=True)

        pos = self.conversion.position([x, y, z, w])
        if self.button_pressed:
            self.current_spell.append([pos["x"], pos["y"]])
        elif self.on_flick_cb is not None:
            flick = self.flick_detector.process_point(
                pos["x"], HEIGHT - pos["y"], now=now
            )
            if flick is not None:
                self._record_activity()
                self.on_flick_cb(flick)

    def _on_battery_notification(self, sender: Any, data: bytearray) -> None:
        """Handle low-battery flag notification (0 = Normal, 1 = Low Battery in official Kano app)."""
        if not data:
            return
        self.battery_low = data[0] == 1
        if self.on_battery_cb:
            self.on_battery_cb(self.battery_low)

    def _on_temperature_notification(self, sender: Any, data: bytearray) -> None:
        """Handle temperature characteristic notification (signed 16-bit little-endian)."""
        if not data or len(data) < 2:
            return
        raw_val = int.from_bytes(data[0:2], byteorder="little", signed=True)
        temp_c = round(raw_val / 100.0, 1) if abs(raw_val) > 120 else float(raw_val)
        if self.temperature is None or abs(temp_c - self.temperature) >= 0.5:
            self.temperature = temp_c
            if self.on_temperature_cb:
                self.on_temperature_cb(self.temperature)

    @staticmethod
    def _flip_cord(coords: list[float]) -> list[float]:
        """Flip Y coordinate for the gesture recognition model."""
        x, y = coords
        return [x, HEIGHT - y]
