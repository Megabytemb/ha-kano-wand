<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/kano_wand/brand/dark_logo@2x.png">
    <source media="(prefers-color-scheme: light)" srcset="custom_components/kano_wand/brand/logo@2x.png">
    <img alt="Kano Wand — Home Assistant Integration" src="custom_components/kano_wand/brand/logo@2x.png" width="420">
  </picture>
</p>

# Kano Wand — Home Assistant Integration

A custom Home Assistant integration for the **Kano Coding Wand**, built on Home Assistant's native Bluetooth (`habluetooth`) and `bleak-retry-connector` architecture. Supports local Bluetooth adapters and **ESPHome Bluetooth Proxies** so you can cast spells in any room of your home.

---

## ✨ Key Features

- **Multi-Room Bluetooth Proxy Roaming**: Uses `bluetooth.async_register_callback` (`connectable=True`) and `bleak-retry-connector` (`establish_connection` with `BleakClientWithServiceCache`). When the wand wakes up in any room, Home Assistant automatically routes the connection through whichever ESPHome Bluetooth Proxy or local adapter has the strongest RSSI.
- **Sleep-Friendly Lifecycle**: Setup succeeds even while the wand is powered off in a drawer. The integration passively listens for the wand's wake-up advertisement and connects in the background within seconds of pressing the wand button.
- **Dynamic Keep-Alive Timeout Slider**: Configurable slider (`number.kano_wand_keep_alive_timeout`, `0`–`30` minutes) controls how long Home Assistant keeps the wand awake after your last button press before letting it power down and freeing the ESP32 proxy connection slot.
- **High-Frequency GATT Stream Isolation**: Quaternion orientation notifications (`~50 Hz`) are buffered and processed purely in memory while the wand button is held down, avoiding Home Assistant State Machine and Recorder database bloat.
- **Local TFLite Spell Recognition**: Recognizes 25 Harry Potter spells on-device using `ai-edge-litert` / `tflite`, loaded asynchronously in an executor thread so the Home Assistant event loop is never blocked.
- **Full Hardware Control**: Control the wand's onboard RGB tip LED (`light.kano_wand_led`) and trigger 7 haptic vibration patterns (`button.kano_wand_vibrate` and `kano_wand.vibrate`).

---

## 📦 Installation

### Option 1: HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Add the URL of this repository with the category **Integration**.
4. Install **Kano Wand** and restart Home Assistant.
5. Turn on your Kano Wand (press the button on the wand)—Home Assistant will automatically discover it under **Settings → Devices & Services**.

### Option 2: Manual Installation
1. Copy the `custom_components/kano_wand` directory into your Home Assistant `<config>/custom_components/kano_wand` folder.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Kano Wand** (or accept the automatic Bluetooth discovery prompt).

---

## 🧩 Entities Provided

| Platform | Entity ID | Name | Description |
| :--- | :--- | :--- | :--- |
| `event` | `event.kano_wand_spell` | **Spell** | Stateless event entity that triggers on every recognized spell (plus `"recentre"` on a short `<0.2s` button tap). Fires reliably even when casting the exact same spell twice in a row. Attributes: `score`, `duration`, `points`. |
| `image` | `image.kano_wand_last_spell_drawing` | **Last Spell Drawing** | Poster-styled PNG diagram of the last wand motion path (with start dot, glowing golden trail, directional arrowhead, spell name, score, duration, and sample count) for easy debugging on dashboards. |
| `sensor` | `sensor.kano_wand_last_spell` | **Last Spell** | Displays the most recently recognized spell name on dashboards. Attributes: `score`, `duration`, `points`. |
| `sensor` | `sensor.kano_wand_battery` | **Battery** | Wand battery level (`%`). |
| `binary_sensor` | `binary_sensor.kano_wand_button` | **Button** | `on` while the wand button is held down; `off` when released. |
| `binary_sensor` | `binary_sensor.kano_wand_connected` | **Connected** | Diagnostic connectivity sensor (`on` when actively connected to a BLE proxy/adapter). |
| `light` | `light.kano_wand_led` | **LED** | RGB light controlling the LED on the tip of the wand (`ColorMode.RGB`). |
| `number` | `number.kano_wand_keep_alive_timeout` | **Keep Alive Timeout** | Configuration slider (`0.0`–`30.0` min, step `0.5` min, default `3.0` min) controlling how long the wand stays awake after activity. Persisted across restarts. |
| `button` | `button.kano_wand_vibrate` | **Vibrate** | Triggers a regular haptic vibration pulse on the wand. |

---

## ⚡ Actions / Services

### `kano_wand.vibrate`
Triggers a haptic vibration pattern on one or all connected Kano Wands.

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `device_id` | `string` / `list` | No | All wands | Target Kano Wand device ID(s). |
| `pattern` | `string` / `int` | No | `"regular"` | One of `"regular"` (`1`), `"short"` (`2`), `"burst"` (`3`), `"long"` (`4`), `"short_long"` (`5`), `"short_short"` (`6`), `"big_pause"` (`7`). |

```yaml
action: kano_wand.vibrate
data:
  pattern: burst
```

---

## 🪄 Recognized Spells (25 Spells + Recentre)

The TFLite model recognizes the following 25 spell gestures (plus `recentre` on a quick button tap):

- `Accio`
- `Aguamenti`
- `Alohomora`
- `Avis`
- `Bombarda`
- `Colovaria`
- `Engorgio`
- `Epoximise`
- `Evanesco`
- `Expelliarmus`
- `Flipendo`
- `Fumos`
- `Gemino`
- `Impedimenta`
- `Incendio`
- `Locomotor`
- `Lumos`
- `Oppugno`
- `Orchideous`
- `Reducio`
- `Reducto`
- `Reparo`
- `Serpensortia`
- `Vermillious`
- `Wingardium Leviosa`

---

## 🤖 Automation Examples

### 1. Triggering on the `event.kano_wand_spell` Entity
Using the `event` entity ensures the automation triggers even if you cast *Lumos* twice in a row:

```yaml
alias: "Kano Wand - Lumos Toggle Living Room Lamp"
triggers:
  - trigger: state
    entity_id: event.kano_wand_spell
    attribute: event_type
    to: "Lumos"
conditions:
  - condition: template
    value_template: "{{ state_attr('event.kano_wand_spell', 'score') | float(0) > 0.60 }}"
actions:
  - action: light.toggle
    target:
      entity_id: light.living_room_lamp
  - action: light.turn_on
    target:
      entity_id: light.kano_wand_led
    data:
      rgb_color: [255, 255, 180]
  - action: kano_wand.vibrate
    data:
      pattern: short
```

### 2. Triggering via the `kano_wand_spell` Event Bus Event
Every spell also fires a `kano_wand_spell` event directly on the Home Assistant event bus:

```yaml
alias: "Kano Wand - Aguamenti Backyard Sprinklers"
triggers:
  - trigger: event
    event_type: kano_wand_spell
    event_data:
      spell: "Aguamenti"
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.score | float(0) > 0.70 }}"
actions:
  - action: kano_wand.vibrate
    data:
      pattern: burst
```

---

## 🧪 Local Development & Live BLE Testing

This repository uses [`uv`](https://docs.astral.sh/uv/) for dependency management and local testing on Windows, macOS, and Linux.

### 1. Install Dependencies
```powershell
uv sync
```

### 2. Run Pytest Test Suite
Runs all unit, integration, TFLite gesture recognition, PNG rendering, and metadata tests:
```powershell
uv run pytest
```

### 3. Run Offline TFLite Gesture Model Check
Verifies `ai-edge-litert` model loading and inference speed without needing BLE hardware:
```powershell
uv run python tests/live_ble_test.py --dry-run
```

### 4. Run Live Interactive BLE Test with a Physical Kano Wand
Uses your computer's built-in Bluetooth adapter to scan for the wand, connect via `bleak-retry-connector`, flash the wand's RGB LED, trigger haptic feedback, and print live quaternion stream rates (`~50 Hz`) and recognized spells as you wave the wand:
```powershell
uv run python tests/live_ble_test.py
```

---

## 📁 Repository Structure

```text
├── custom_components/
│   └── kano_wand/
│       ├── model/
│       │   └── model.tflite      # TFLite spell recognition model
│       ├── translations/
│       │   └── en.json
│       ├── __init__.py           # Integration setup, BLE callbacks & services
│       ├── binary_sensor.py      # Button & Connected binary sensors
│       ├── button.py             # Vibrate button entity
│       ├── config_flow.py        # Bluetooth discovery & user config flow
│       ├── const.py              # GATT UUIDs, spells & constants
│       ├── conversion.py         # Quaternion-to-2D Euler projection math
│       ├── drawing.py            # Pure-NumPy poster-styled PNG spell path renderer
│       ├── entity.py             # Base entity & DeviceInfo with BLE connection link
│       ├── event.py              # Stateless Spell EventEntity
│       ├── fitCurves.py          # Cubic Bezier curve fitting for spell paths
│       ├── gesture.py            # TFLite / LiteRT gesture inference
│       ├── image.py              # Last Spell Drawing ImageEntity
│       ├── light.py              # RGB565 Wand Tip LED LightEntity
│       ├── manifest.json         # HA integration manifest & BLE matchers
│       ├── number.py             # Keep Alive Timeout slider (RestoreNumber)
│       ├── sensor.py             # Last Spell & Battery sensors
│       ├── services.yaml         # Service definitions for UI
│       ├── strings.json          # UI strings
│       └── wand.py               # KanoWand BLE client (bleak-retry-connector)
├── tests/
│   ├── conftest.py               # Shared pytest fixtures & HA test stubs
│   ├── live_ble_test.py          # Interactive CLI live hardware BLE test harness
│   ├── test_config_flow.py       # Bluetooth & user config flow tests
│   ├── test_drawing.py           # Poster PNG renderer tests
│   ├── test_entities.py          # Home Assistant entity & BLE lifecycle tests
│   ├── test_gesture.py           # TFLite spell recognition & fitCurve tests
│   └── test_metadata.py          # Manifest, HACS, translation & brand PNG tests
├── hacs.json                     # HACS repository metadata
├── pyproject.toml                # Project dependencies for uv
└── README.md
```
