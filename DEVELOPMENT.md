# SmallTV Ultra – Development Guide

## Project layout

```
/home/kizs/work/claude/smalltv/pro/
├── custom_components/smalltv_ultra/   ← integration source
│   ├── __init__.py                    setup_entry, unload_entry, reload listener
│   ├── manifest.json                  domain, version, requirements, issue_tracker
│   ├── const.py                       DOMAIN, CONF_*, DEFAULT_*, PLATFORMS, MODE_*
│   ├── api.py                         async HTTP client (aiohttp)
│   ├── config_flow.py                 UI wizard (IP input) + OptionsFlow
│   ├── coordinator.py                 DataUpdateCoordinator – fetch/GIF/upload loop
│   ├── image_processor.py             Pillow – crop/resize/label/GIF encode
│   ├── light.py                       brightness entity
│   ├── number.py                      refresh_interval + cycle_interval entities
│   ├── button.py                      force_refresh entity
│   ├── select.py                      display_mode entity (cameras/builtin)
│   ├── strings.json                   Hungarian UI strings
│   └── translations/en.json           English UI strings
├── .github/workflows/
│   ├── hassfest.yaml                  HA integration validator (runs on every push)
│   └── hacs_validation.yaml           HACS validator (runs on every push)
├── README.md                          User-facing docs (shown in HACS)
├── hacs.json                          HACS metadata
├── SMALLTV_ULTRA_DEV.md               Full device API reference
└── DEVELOPMENT.md                     This file
```

---

## Deploy changes to HAOS (dev workflow)

```python
# Upload one or more changed files via SFTP
import paramiko

HOST, PORT, USER, PASS = "homeassistant.local", 22222, "root", "<password>"
REMOTE = "/config/custom_components/smalltv_ultra"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
sftp = client.open_sftp()
sftp.put("custom_components/smalltv_ultra/coordinator.py", f"{REMOTE}/coordinator.py")
sftp.close()

# Restart HA core (wait ~30s)
client.exec_command("ha core restart")
client.close()
```

After HA restarts, press **Force Refresh** in HA to trigger an immediate coordinator run.

To read logs:
```python
_, stdout, _ = client.exec_command("ha core logs 2>/dev/null | grep -i 'smalltv' | tail -40")
print(stdout.read().decode())
```

---

## Architecture – how it works

```
HA startup
  └─ async_setup_entry()
       ├─ SmallTVApi(host, session)          aiohttp client
       ├─ SmallTVUltraCoordinator(...)       DataUpdateCoordinator
       │    update_interval = refresh_interval
       └─ async_forward_entry_setups()       loads light/number/button/select

Every refresh_interval seconds (or Force Refresh):
  SmallTVUltraCoordinator._async_update_data()
    ├─ GET /v.json                           ping + firmware version
    ├─ [cameras mode]
    │    ├─ async_get_image() × N cameras    fetch JPEG from HA camera entities
    │    ├─ executor_job(create_camera_gif)  Pillow: crop → resize → label → GIF
    │    ├─ [first run] GET /set?theme=3     switch to Photo Album mode
    │    ├─ [first run] GET /set?clear=image wipe old images
    │    ├─ POST /doUpload  cameras.gif      upload animated GIF
    │    └─ GET /set?gif=/image//cameras.gif display it
    └─ [builtin mode]
         └─ GET /app.json                   just read current theme, no upload
```

### _needs_album_init flag

Set to `True` on:
- Integration startup
- `async_force_refresh()` (Force Refresh button)
- Mode switch to `cameras` (via select entity)

When `True`: sends `set_theme(3)` + `clear_images()` before uploading.
Set to `False` after successful upload + display.

---

## Known device quirks (ESP8266 / stock firmware V9.0.45)

| Issue | Cause | Fix applied |
|---|---|---|
| `POST /doUpload` returns duplicate `Content-Length` header | ESP8266 firmware bug | Catch `aiohttp.ClientResponseError` where `"Duplicate Content-Length" in str(exc)` → treat as success |
| `/set?img=` only works in Photo Album mode | Firmware design | Always call `set_theme(3)` before image ops |
| `/set?gif=` path needs double slash | Firmware quirk | Use `/image//cameras.gif` (not `/image/cameras.gif`) |
| `aiohttp.FormData` emits duplicate Content-Length on some versions | aiohttp bug | Build multipart body manually as raw bytes |
| Old images remain visible in Photo Album | Album shows all files in /image/ | Call `GET /set?clear=image` before first upload |
| `/api/update` returns 404 | Only exists on SmallTV Pro, not Ultra | Don't use it |

---

## Known HA / Python quirks

| Issue | Fix |
|---|---|
| `OptionsFlow.__init__` setting `self.config_entry` raises `AttributeError` on Python 3.13 | Remove `__init__` entirely – HA sets `config_entry` internally |
| `async_get_options_flow` must not pass `config_entry` to constructor | Return `SmallTVUltraOptionsFlow()` with no arguments |
| `manifest.json` keys must be sorted: `domain`, `name`, then alphabetical | Required by hassfest |

---

## GIF generation (image_processor.py)

```
For each camera:
  1. async_get_image(hass, entity_id)   → raw JPEG/PNG bytes
  2. _process_frame(raw, label)          → PIL Image (RGB, 240×240)
     a. convert("RGB")
     b. center crop to square
     c. resize to 240×240 (LANCZOS)
     d. alpha_composite semi-transparent label bar at bottom
  3. quantize(colors=256, MEDIANCUT)    → GIF-compatible palette image

create_camera_gif(frames, frame_duration_s):
  → first_frame.save(GIF, save_all=True, append_images=rest,
                     duration=ms, loop=0, optimize=True)
  → returns bytes
```

GIF is uploaded as `cameras.gif` and overwritten on every refresh (no new filename = no extra flash wear).

---

## Entities reference

| Entity ID | Platform | HA scale | Device scale | Notes |
|---|---|---|---|---|
| `light.smalltv_ultra_brightness` | light | 0–255 | 0–100 via `/set?brt=` | State stored locally (device has no read-back endpoint) |
| `number.smalltv_ultra_refresh_interval` | number | 60–3600 s | – | Stored in options; changing it reloads the entry |
| `number.smalltv_ultra_cycle_interval` | number | 1–10 s | `/set?i_i=` | Also applied live on change |
| `button.smalltv_ultra_force_refresh` | button | – | – | Sets `_needs_album_init=True`, calls `async_refresh()` |
| `select.smalltv_ultra_display_mode` | select | cameras/builtin | `set_theme(3/1)` | Stored in options |

---

## HACS publication status

| Step | Status |
|---|---|
| GitHub repo | ✅ https://github.com/kizs/smalltv-cameras |
| Hassfest Action | ✅ passing |
| HACS validation Action | ✅ 7/8 passing |
| home-assistant/brands PR | ⏳ open manually: https://github.com/home-assistant/brands/compare/master...kizs:brands:add-smalltv-ultra?expand=1 |
| hacs/default PR | ⏳ open manually: https://github.com/hacs/default/compare/master...kizs:default:add-smalltv-ultra?expand=1 |

Once both PRs are merged, the integration appears in the HACS default store.
Custom repo install works today: HACS → Integrations → ⋮ → Custom repositories → `https://github.com/kizs/smalltv-cameras`

---

## Ideas for future development

- **Sensor entities** – expose storage space (`/space.json`) as a sensor
- **Camera image overlay** – add timestamp or HA state values as text on frames
- **Higher GIF resolution** – test 240×240 stability; offer configurable size
- **Multiple GIF files** – one per camera, cycle via album instead of animated GIF
- **Service call** – `smalltv_ultra.display_image` to show an arbitrary image URL
- **Night mode** – auto-reduce brightness on schedule (`/set?t1=...&t2=...`)
- **MJPEG streaming** – for cameras that support it, capture N frames for smoother GIF
- **Config entry diagnostics** – implement `async_get_config_entry_diagnostics()`
- **Translations** – add more language files under `translations/`
