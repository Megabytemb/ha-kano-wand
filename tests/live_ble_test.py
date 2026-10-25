"""Live BLE integration test harness for Kano Wand on Windows/macOS/Linux.

Usage:
  uv run python tests/live_ble_test.py            # Live scan, connect, and interactive spell test
  uv run python tests/live_ble_test.py --dry-run  # Verify TFLite model & synthetic spell pipeline
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from pathlib import Path
import sys
import time
import types
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Allow importing custom_components.kano_wand submodules without executing
# custom_components/kano_wand/__init__.py (which imports homeassistant).
ROOT_DIR = Path(__file__).resolve().parent.parent
COMPONENT_DIR = ROOT_DIR / "custom_components" / "kano_wand"

pkg_root = types.ModuleType("custom_components")
pkg_root.__path__ = [str(ROOT_DIR / "custom_components")]
sys.modules.setdefault("custom_components", pkg_root)

pkg_wand = types.ModuleType("custom_components.kano_wand")
pkg_wand.__path__ = [str(COMPONENT_DIR)]
sys.modules.setdefault("custom_components.kano_wand", pkg_wand)

from custom_components.kano_wand.const import (  # noqa: E402
    SERVICE_INFO,
    SERVICE_IO,
    SERVICE_SENSOR,
    VIBRATION_REGULAR,
)
from custom_components.kano_wand.drawing import render_spell_png  # noqa: E402
from custom_components.kano_wand.gesture import GestureSpells  # noqa: E402
from custom_components.kano_wand.wand import KanoWand  # noqa: E402

KANO_UUIDS = {
    SERVICE_INFO.lower(),
    SERVICE_IO.lower(),
    SERVICE_SENSOR.lower(),
}


def is_kano_advertisement(
    device: BLEDevice, adv: AdvertisementData, target_address: str | None = None
) -> bool:
    """Return True if the BLE advertisement matches a Kano Wand."""
    if target_address and device.address.upper() == target_address.upper():
        return True
    name = adv.local_name or device.name or ""
    if name.startswith("Kano-Wand"):
        return True
    for uuid in adv.service_uuids or []:
        if uuid.lower() in KANO_UUIDS:
            return True
    return False


async def run_dry_test() -> int:
    """Test TFLite gesture model and KanoWand state machine without hardware."""
    print("=== Running Kano Wand Dry-Run Verification ===")
    t0 = time.perf_counter()
    gs = GestureSpells(load_immediately=True)
    dt = (time.perf_counter() - t0) * 1000
    print(f"[OK] Loaded TFLite model ({gs.numberOfspells} spells) in {dt:.1f} ms")

    # Test synthetic vertical/Lumos-like stroke
    synthetic_points = [[400.0, float(500 - i * 10)] for i in range(25)]
    synthetic_points += [[float(400 + i * 8), 250.0] for i in range(15)]
    res = gs.recognise(synthetic_points)
    print(f"[OK] Synthetic gesture inference result: {res}")

    # Test zero-movement edge case (should not raise ZeroDivisionError)
    zero_points = [[400.0, 300.0] for _ in range(10)]
    res_zero = gs.recognise(zero_points)
    print(f"[OK] Zero-movement guard result: {res_zero}")

    events: list[tuple[str, Any]] = []
    wand = KanoWand(
        ble_device_callback=lambda: None,
        name="Kano-Wand-Test",
        on_button=lambda b: events.append(("button", b)),
        on_spell=lambda s: events.append(("spell", s)),
        on_battery=lambda b: events.append(("battery", b)),
        on_connected=lambda c: events.append(("connected", c)),
        on_led=lambda on, rgb: events.append(("led", (on, rgb))),
        gesture_spells=gs,
    )
    wand.set_keep_alive_timeout(4.5)
    assert wand.keep_alive_timeout_minutes == 4.5

    # Simulate short button press (<0.2s) -> recentre
    wand._on_button_notification(None, bytearray([1]))
    await asyncio.sleep(0.05)
    wand._on_button_notification(None, bytearray([0]))
    await asyncio.sleep(0.02)

    print(f"[OK] Simulated button click emitted events: {events}")
    print("=== Dry-Run Verification Passed! ===")
    return 0


async def run_live_ble_test(
    duration: float, keep_alive_minutes: float, target_address: str | None = None
) -> int:
    """Scan for a physical Kano Wand, connect via bleak-retry-connector, and log live events."""
    print("==================================================================")
    print("  Kano Wand — Live Home Assistant BLE Integration Test Harness")
    print("==================================================================")
    print("Turn on your Kano Wand now (press the button on the wand)...")
    if duration > 0:
        print(f"Listening for BLE advertisements and events for {duration:.0f}s (Ctrl+C to stop)\n")
    else:
        print("Listening for BLE advertisements and events until Ctrl+C...\n")

    latest_device: BLEDevice | None = None
    scanner_running = False
    connecting = False
    found_event = asyncio.Event()

    def on_connected(connected: bool) -> None:
        state_str = "CONNECTED" if connected else "DISCONNECTED"
        print(f"\n[HA Entity] binary_sensor.kano_wand_connected -> {state_str}")
        if connected:
            print(
                "--> Wand is READY (burst vibrate)! Hold the button and draw a spell "
                "in the air, or short-click the button to recentre.\n"
            )
        else:
            # Wake up scanner loop to listen for next wake-up advertisement
            found_event.set()

    def on_battery(batt: int) -> None:
        print(f"[HA Entity] sensor.kano_wand_battery -> {batt}%")

    def on_button(pressed: bool) -> None:
        state_str = "ON (holding button - recording spell...)" if pressed else "OFF"
        print(
            f"[HA Entity] binary_sensor.kano_wand_button -> {state_str} "
            f"(GATT stream: {wand.quaternion_rate_hz:.1f} Hz)"
        )

    def on_led(is_on: bool, rgb: tuple[int, int, int]) -> None:
        print(f"[HA Entity] light.kano_wand_led -> {'ON' if is_on else 'OFF'} RGB={rgb}")

    def on_spell(spell_data: dict[str, Any]) -> None:
        spell = spell_data.get("spell")
        score = spell_data.get("score", 0.0)
        dur = spell_data.get("duration", 0.0)
        pts = spell_data.get("points", 0)
        runner_up = spell_data.get("runner_up")
        runner_up_score = spell_data.get("runner_up_score", 0.0)
        extra = (
            f", 2nd='{runner_up}' ({runner_up_score:.1%})"
            if runner_up and spell != "recentre"
            else ""
        )
        print(
            f"\n✨ [HA Entity] event.kano_wand_spell & sensor.kano_wand_last_spell -> "
            f"'{spell}' (score={score:.2%}, duration={dur:.2f}s, samples={pts}{extra})"
        )
        if spell_data.get("positions"):
            out_path = ROOT_DIR / "last_spell.png"
            out_path.write_bytes(render_spell_png(spell_data))
            print(
                f"🖼️  [HA Entity] image.kano_wand_last_spell_drawing updated "
                f"(saved debug preview to {out_path.name})"
            )
        if spell and spell not in ("not a Spell", "recentre"):
            asyncio.create_task(_spell_feedback())

    # Start scanner BEFORE loading TFLite so BLE discovery begins at 0ms
    def detection_callback(device: BLEDevice, adv: AdvertisementData) -> None:
        nonlocal latest_device
        if not is_kano_advertisement(device, adv, target_address):
            return

        latest_device = device
        wand.name = adv.local_name or device.name or f"Kano-Wand ({device.address})"
        if not wand.is_connected and not connecting:
            print(
                f"[BLE Discovered] {wand.name} ({device.address}) "
                f"RSSI={adv.rssi} dBm -> Stopping scan & connecting immediately..."
            )
            found_event.set()

    scanner = BleakScanner(
        detection_callback=detection_callback,
        scanning_mode="active",
    )
    await scanner.start()
    scanner_running = True

    gs = GestureSpells(load_immediately=True)
    wand = KanoWand(
        ble_device_callback=lambda: latest_device,
        name="Kano Wand",
        on_button=on_button,
        on_spell=on_spell,
        on_battery=on_battery,
        on_connected=on_connected,
        on_led=on_led,
        gesture_spells=gs,
        vibrate_on_connect=True,
    )
    wand.set_keep_alive_timeout(keep_alive_minutes)

    async def _spell_feedback() -> None:
        """Brief green LED flash & pulse when a spell is recognized."""
        try:
            await wand.set_led(True, (0, 255, 100))
            await wand.vibrate(VIBRATION_REGULAR)
            await asyncio.sleep(0.6)
            await wand.set_led(True, (148, 0, 211))
        except Exception:
            pass

    try:
        start = time.monotonic()
        while True:
            if duration > 0:
                remaining = duration - (time.monotonic() - start)
                if remaining <= 0:
                    break
            else:
                remaining = 3600.0

            if not wand.is_connected:
                if not scanner_running:
                    await scanner.start()
                    scanner_running = True
                found_event.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(found_event.wait(), timeout=min(1.0, remaining))

                if latest_device is not None and not wand.is_connected:
                    connecting = True
                    # Pause active scanning while connecting to avoid radio contention
                    if scanner_running:
                        await scanner.stop()
                        scanner_running = False
                    await wand.ensure_connected(latest_device)
                    connecting = False
            else:
                await asyncio.sleep(0.5)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("\nStopping scanner and disconnecting wand...")
        if scanner_running:
            with contextlib.suppress(Exception):
                await scanner.stop()
        await wand.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kano Wand Live BLE Test Harness")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run offline model & state-machine check without BLE hardware",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Optional session limit in seconds (default: 0 = run until Ctrl+C)",
    )
    parser.add_argument(
        "--keep-alive",
        type=float,
        default=3.0,
        help="Keep-alive timeout in minutes (default: 3.0)",
    )
    parser.add_argument(
        "--address",
        type=str,
        default=None,
        help="Optional MAC address (e.g. E0:D2:39:11:C9:05) for instant match before scan response",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.dry_run:
        return asyncio.run(run_dry_test())
    return asyncio.run(run_live_ble_test(args.duration, args.keep_alive, args.address))


if __name__ == "__main__":
    raise SystemExit(main())
