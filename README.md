# SmallTV Ultra – Home Assistant Integration

A Home Assistant custom integration for the **GeekMagic SmallTV Ultra** (ESP8266, 240×240 IPS display).

Displays your Home Assistant camera feeds as an animated GIF on the device – no custom firmware required.

---

## Features

- 📷 Shows all your configured cameras as a **looping animated GIF**
- ⏱️ Configurable frame speed (Cycle Interval) and upload frequency (Refresh Interval)
- 💡 Brightness control via a **light entity**
- 🔄 **Force Refresh** button for immediate update
- 🖼️ Switch between **camera mode** and the device's built-in themes
- Works with the **stock firmware** (V9.0.45 tested) – no flashing needed

---

## Requirements

- Home Assistant 2024.1 or newer
- GeekMagic SmallTV Ultra with firmware **V9.0.45** or newer
- The device must be reachable on your local network (HTTP, port 80)
- At least one `camera` entity in Home Assistant

---

## Installation

### Option A – HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add this repository URL, category: **Integration**
3. Click **SmallTV Ultra** → **Download**
4. Restart Home Assistant

### Option B – Manual

1. Copy the `custom_components/smalltv_ultra/` folder to your HA config:
   ```
   /config/custom_components/smalltv_ultra/
   ```
2. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **SmallTV Ultra**
3. Enter the **IP address** of your device (e.g. `192.168.0.18`)
   - You can find it in your router's DHCP table, or check the device's WiFi settings page
   - The integration validates the connection against `/v.json` before saving

---

## Configuration

After adding the device, click **Configure** to set up display options:

| Setting | Description | Default |
|---|---|---|
| **Camera entities** | Cameras to display (multi-select) | – |
| **Refresh Interval** | How often HA regenerates and uploads the GIF (seconds) | 300 s |
| **Cycle Interval** | How long each camera frame is shown in the GIF (seconds) | 1 s |
| **Display Mode** | `cameras` = animated GIF / `builtin` = device's own themes | cameras |

> ⚠️ **Flash wear notice:** The device stores images on NOR flash (~100 000 write cycles).
> Keep the Refresh Interval at **60 seconds or more** to avoid premature wear.
> The recommended interval for daily use is **5–15 minutes**.

---

## Entities

| Entity | Type | Description |
|---|---|---|
| `light.smalltv_ultra_brightness` | Light | Display brightness (0–100 %) |
| `number.smalltv_ultra_refresh_interval` | Number | HA upload frequency (60–3600 s) |
| `number.smalltv_ultra_cycle_interval` | Number | GIF frame duration (1–10 s) |
| `button.smalltv_ultra_force_refresh` | Button | Immediate camera fetch + upload |
| `select.smalltv_ultra_display_mode` | Select | Switch between `cameras` and `builtin` |

---

## How It Works

```
Home Assistant cameras
        ↓  async_get_image()
Image processor (Pillow)
  • center crop → 240×240
  • label bar with camera name
  • all frames → animated GIF
        ↓  POST /doUpload?dir=/image/
SmallTV Ultra HTTP API
  GET /set?gif=/image//cameras.gif
        ↓
240×240 IPS display
```

---

## Supported Devices

| Device | Status |
|---|---|
| SmallTV Ultra (ESP8266, 240×240) | ✅ Tested |
| SmallTV Pro | ❌ Different API – not supported |

---

## Troubleshooting

**"Config flow could not be loaded"** after clicking Configure
→ Make sure you are running HA 2024.1+. Older versions had a different OptionsFlow API.

**Device shows old/extra pictures**
→ Press **Force Refresh**. On first run the integration clears the `/image/` folder automatically.

**No image on device after setup**
→ Check **Settings → Devices & Services → SmallTV Ultra** – the integration log shows upload status. Confirm the device IP is reachable from your HA server.

**GIF looks washed out / poor quality**
→ GIF format is limited to 256 colours per frame. This is a GIF format limitation, not a bug.

---

## License

MIT
