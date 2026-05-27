# GAF MasterFlow Vent Control — Home Assistant integration

Unofficial Home Assistant custom component for the **GAF MasterFlow Smart
Attic Fan / Vent Control** system. Talks to GAF's cloud (operated by Keen
Home) at two HTTPS hosts reverse-engineered from the official "Vent Control"
Android app (`com.gaf.quickconnectapp` v1.0.9):

| Purpose             | Host                                         |
|---------------------|----------------------------------------------|
| AWS Cognito auth    | `https://gaf-coreservices.aurai.io/cognito/` |
| Device & config API | `https://gaf.keenhome.io/gaf/`               |

## Install

1. Copy the entire `gaf_masterflow/` folder into your HA config directory at
   `config/custom_components/gaf_masterflow/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → "GAF MasterFlow
   Vent Control". Enter the same email / password you use in the mobile app.

## Entities created per device

* **Sensors** (set-points, mode, diagnostics):
  Set temperature, Set humidity, Timer value, Mode, Signal strength,
  Firmware version, plus disabled-by-default diagnostic sensors for the
  account-wide defaults and serial number.
* **Binary sensors**: Verified (connectivity), OTA in progress, Automatic
  mode, Timer mode, Fan mode, Humidity monitor.
* **Switches** (mutually exclusive on the firmware side): Automatic Mode,
  Timer Mode, Fan Mode.
* **Buttons**: Turn all off, Check for firmware update.

## Branding

Brand images live in `brand/` (HA 2026.3+ picks them up automatically):

```
gaf_masterflow/
├── brand/
│   ├── icon.png         (256×256)
│   ├── icon@2x.png      (512×512)
│   ├── logo.png         (256×256)
│   └── logo@2x.png      (512×512)
```

The GAF logo was extracted from the Android app's bundled assets at
`res/drawable-mdpi-v4/src_assets_gaf_log_img.png` and upscaled.

## API notes / caveats

* **No live readings.** The cloud API only exposes configured set-points
  (`setTemperature`, `setHumidity`) and mode flags. Actual measured
  temperature/humidity from the device sensors is not surfaced through
  this API.
* **Inconsistent field names.** The READ side uses
  `setTemperature` / `setHumidity`; the WRITE side (POST `/gaf/deviceMode/{id}`)
  uses `desiredTemp` / `desiredHumidity`. Sending the read-side names back
  on a write returns HTTP 417 with `statusCode 4444`.
* **Firmware update**: two-step — GET `fw/fwInfo` to discover
  `latest_fw_version_available`, then PUT `fw/fwUpdate?device_id=&fw_version=`.
* **Account role**: the app defaults to `userRole: "contractor"`. The
  integration exposes this in the config flow if you need to switch to
  `"consumer"`.

## Disclaimer

Not affiliated with GAF, Standard Industries, or Keen Home. Cloud APIs can
change without notice. Use at your own risk.
