# SmallTV – Home Assistant Integration

A Home Assistant custom integration for **GeekMagic SmallTV Ultra** and **SmallTV Pro** (ESP8266, 240×240 IPS display).

Displays your Home Assistant camera feeds as an animated GIF on the device – no custom firmware required.

---

## Features

- 📷 Shows all your configured cameras as a **looping animated GIF**
- ⏱️ Configurable frame speed (Cycle Interval) and upload frequency (Refresh Interval)
- 💡 Brightness control via a **light entity**
- 🔄 **Force Refresh** button for immediate update
- 🖼️ Switch between **camera mode** and the device's built-in themes (Ultra only)
- 🔍 **Automatic network scan** – finds devices on your subnet without typing IPs
- Works with the **stock firmware** – no flashing needed

---

## Supported Devices

| Device | Firmware tested | Camera GIF | Built-in themes |
|---|---|---|---|
| SmallTV **Ultra** (ESP8266, 240×240) | V9.0.45 | ✅ | ✅ |
| SmallTV **Pro** (ESP8266, 240×240) | V3.3.76EN | ✅ | ✅ |

Both models use the same animated GIF pipeline. The only difference is that the Pro does not support the album cycle interval setting (the GIF frame speed is still configurable from HA).

---

## Requirements

- Home Assistant 2024.1 or newer
- GeekMagic SmallTV Ultra (V9.0.45+) or SmallTV Pro (V3.3.76EN+)
- The device must be reachable on your local network (HTTP, port 80)
- At least one `camera` entity in Home Assistant

---

## Installation

### Option A – HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add this repository URL, category: **Integration**
3. Click **SmallTV** → **Download**
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
3. Choose **Scan network** or **Enter IP manually**

### Scan network
Enter the first three octets of your subnet (e.g. `192.168.0`). The integration probes all 254 hosts concurrently and lists every SmallTV it finds – both Ultra and Pro.

> **Note:** mDNS does not cross subnet boundaries. If your SmallTV devices are on a different subnet from HA (e.g. an IoT VLAN), use the scan with the correct subnet prefix.

### Enter IP manually
Type the device IP directly (e.g. `192.168.0.18`). The integration validates it against the device API before saving.

---

## Configuration

After adding the device, click **Configure** to set up display options:

| Setting | Description | Default |
|---|---|---|
| **Camera entities** | Cameras to display (multi-select) | – |
| **Refresh Interval** | How often HA regenerates and uploads the GIF (seconds) | 300 s |
| **Cycle Interval** | How long each camera frame is shown in the GIF (seconds) | 1 s |
| **Display Mode** | `cameras` = animated GIF / `builtin` = device's own themes | cameras |

> ⚠️ **Flash wear notice:** The device stores images on NOR flash (~100 000 write cycles per sector).
> Keep the Refresh Interval at **60 seconds or more**. The filesystem's wear levelling means
> the real lifespan is far longer than the raw number suggests, but 5–15 minutes is recommended for daily use.

### Change IP address

If your device gets a new IP, go to **Settings → Devices & Services → SmallTV → ⋮ → Reconfigure**.

---

## Entities

| Entity | Type | Description |
|---|---|---|
| `light.*_brightness` | Light | Display brightness (0–100 %) |
| `number.*_refresh_interval` | Number | HA upload frequency (60–3600 s) |
| `number.*_cycle_interval` | Number | GIF frame duration (1–10 s) |
| `button.*_force_refresh` | Button | Immediate camera fetch + upload |
| `select.*_display_mode` | Select | Switch between `cameras` and `builtin` |

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
SmallTV HTTP API
  GET /set?gif=/image//cameras.gif
        ↓
240×240 IPS display
```

---

## Troubleshooting

**"Config flow could not be loaded"** after clicking Configure
→ Make sure you are running HA 2024.1+.

**Device shows old/extra pictures**
→ Press **Force Refresh**. On first run the integration clears the `/image/` folder automatically.

**No image on device after setup**
→ Check **Settings → Devices & Services → SmallTV** – the integration log shows upload status. Confirm the device IP is reachable from your HA server.

**Scan finds no devices**
→ Check the subnet prefix. If HA and the SmallTV are on different subnets, enter the SmallTV's subnet (e.g. `192.168.0` if the device is at `192.168.0.x`).

**GIF looks washed out / poor quality**
→ GIF format is limited to 256 colours per frame. This is a GIF format limitation, not a bug.

---

## License

Apache 2.0
