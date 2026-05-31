# GAF MasterFlow Vent Control — Home Assistant Integration

[![hacs][hacs-badge]][hacs-url]
[![HACS validation][validate-badge]][validate-url]
[![hassfest][hassfest-badge]][hassfest-url]
[![License: MIT][license-badge]](LICENSE)

Unofficial Home Assistant custom integration for the **GAF MasterFlow Smart
Attic Fan / Vent Control** system.

It talks to GAF's cloud (operated by Keen Home) over two HTTPS hosts that were
reverse-engineered from the official **"Vent Control"** Android app
(`com.gaf.quickconnectapp`, v1.0.9). No app, no local API access, and no
additional Python dependencies are required — the integration uses Home
Assistant's built-in `aiohttp` session.

> **Not affiliated with GAF, Standard Industries, or Keen Home.** This is a
> community project that uses an undocumented cloud API. See the
> [Disclaimer](#disclaimer).

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Features

- **Cloud login** with the same email / password you use in the mobile app
  (AWS Cognito), with automatic token refresh on expiry.
- **Multi-device** support — every fan on the account is created as its own HA
  device with its own entities.
- **Live readings** for temperature and humidity, plus a derived **Running**
  sensor that infers whether the fan is actually blowing.
- **Full control** of operating mode, set-points, and timer duration, exposed
  both as a clean `Mode` dropdown and as individual switches for automations.
- **Firmware** version reporting and a one-press OTA update check.
- A 30-second polling interval so HA stays reasonably fresh after changes made
  in the app.

---

## Requirements

| Requirement        | Value                                  |
|--------------------|----------------------------------------|
| Home Assistant     | 2024.1.0 or newer                      |
| Integration type   | Hub (`cloud_polling`)                  |
| Account            | An existing GAF / Vent Control account |
| Extra dependencies | None                                   |

You must already have a working account in the **Vent Control** mobile app and
at least one paired fan. This integration does not create accounts or pair new
hardware.

---

## Installation

### Option A — HACS (recommended)

If the integration is available in HACS, search for **GAF MasterFlow Vent
Control**, install it, and restart Home Assistant.

Otherwise, add it as a custom repository:

1. In HACS, open the **⋮** menu → **Custom repositories**.
2. Add `https://github.com/hitchin999/GAFVentControl-HA` with category
   **Integration**.
3. Search for **GAF MasterFlow Vent Control** in HACS and install it.
4. Restart Home Assistant.

### Option B — Manual

1. Copy the `custom_components/gaf_masterflow/` folder into your HA config
   directory so it lands at:
   ```
   config/custom_components/gaf_masterflow/
   ```
2. Restart Home Assistant.

---

## Configuration

After installing and restarting:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **GAF MasterFlow Vent Control**.
3. Sign in:

   | Field        | Notes                                                          |
   |--------------|----------------------------------------------------------------|
   | Email        | Same email used in the Vent Control app.                       |
   | Password     | Same password used in the app.                                 |
   | Account type | `contractor` (default) or `consumer`. Match your app account.  |

Each account can only be added once. If sign-in fails you'll see *Invalid email
or password* (bad credentials) or *Cannot reach the GAF cloud service* (network
or server-side issue — HA will retry automatically).

---

## Entities

Every fan on the account gets its own device. The following entities are
created per device.

### Sensors

| Entity             | Unit | Notes                                                      |
|--------------------|------|------------------------------------------------------------|
| Temperature        | °F   | Live reading from the device.                              |
| Humidity           | %    | Live reading from the device.                              |
| Signal strength    | —    | Diagnostic.                                                |
| Firmware version   | —    | Diagnostic.                                                |
| Serial number      | —    | Diagnostic, **disabled by default**.                       |

### Binary sensors

| Entity                  | Device class | Notes                                                                       |
|-------------------------|--------------|-----------------------------------------------------------------------------|
| Running                 | running      | **Inferred** — see [How it works](#how-it-works). Not reported directly.    |
| Verified                | connectivity | Whether the device is verified / connected.                                 |
| OTA update in progress  | update       | Diagnostic.                                                                 |
| Automatic mode          | running      | Mirrors the active-mode flag.                                               |
| Timer mode              | running      | Mirrors the active-mode flag.                                               |
| Manual mode             | running      | Mirrors the active-mode flag (the API calls this `fanMode`).                |
| Humidity monitor        | running      | Whether humidity-based activation is enabled.                               |

### Controls

| Entity                 | Type   | Range / options                          | Notes                                                                 |
|------------------------|--------|------------------------------------------|-----------------------------------------------------------------------|
| Mode                   | select | `Off` / `Automatic` / `Timer` / `Manual` | The recommended way to switch modes — they're mutually exclusive.     |
| Automatic mode         | switch | on / off                                 | Convenience switch; turning one on clears the other two.              |
| Timer mode             | switch | on / off                                 | Convenience switch.                                                   |
| Manual mode            | switch | on / off                                 | Convenience switch.                                                   |
| Activation temperature | number | 90–120 °F, 1 °F step                     | Temperature set-point for Automatic mode.                            |
| Activation humidity    | number | 30–80 %, 1 % step                        | Humidity set-point for Automatic mode.                               |
| Timer duration         | number | 30–360 min, 30-min step                  | How long Timer mode runs (max 6 hours).                              |

### Buttons

| Entity                    | Notes                                                          |
|---------------------------|----------------------------------------------------------------|
| Turn all off              | Clears all three mode flags in a single request.               |
| Refresh now               | Forces an immediate cloud poll (diagnostic).                   |
| Check for firmware update | Looks up the latest firmware and triggers an OTA if newer (diagnostic). |

> **Mode vs. switches.** The `Mode` select and the three mode switches control
> the same underlying flags. The flags are mutually exclusive on the device, so
> turning on one switch automatically turns the other two off. Use whichever
> fits your dashboard or automation; the `Mode` select is usually cleaner.

---

## How it works

The integration polls `deviceList` every 30 seconds and enriches each entry
with its detail payload, then maps the cloud's fields onto HA entities.

A few behaviours are worth knowing:

- **Live readings vs. set-points.** The cloud uses confusingly similar field
  names. The integration treats `deviceConfig.setTemperature` /
  `deviceConfig.setHumidity` as the **live** readings (the Temperature/Humidity
  sensors), and `deviceSettings.setTemperature` / `deviceSettings.setHumidity`
  as the **target set-points** (the Activation temperature/humidity numbers).

- **The "Running" binary sensor is inferred.** The API never reports run state
  directly, so it's computed:
  - **Manual mode on** → running.
  - **Timer mode on** → running (the device clears the flag when the timer
    expires, so the flag being set implies it's still active).
  - **Automatic mode** → running if live temperature ≥ activation temperature,
    or (humidity monitor on and live humidity ≥ activation humidity).
  - Otherwise → off.

- **Token handling.** Login returns a Cognito `idToken` that's sent as the
  literal `Authorization` header (no `Bearer` prefix). On a `401`/`403` the
  client transparently re-logs in once and retries.

---

## Troubleshooting

- **Sign-in keeps failing.** Confirm the email/password work in the mobile app,
  and that the **Account type** matches (most app accounts are `contractor`).

- **No entities / fan missing.** Make sure the fan is paired and visible in the
  app first. The integration only surfaces devices the cloud returns in
  `deviceList`.

- **A control didn't "stick."** Writes are confirmed on the next poll (up to
  30 seconds), or press **Refresh now**. If a write fails with a server error,
  enable debug logging (below) to see the exact request body.

- **Enable debug logging:**
  ```yaml
  # configuration.yaml
  logger:
    default: info
    logs:
      custom_components.gaf_masterflow: debug
  ```

---

## Disclaimer

This project is not affiliated with, endorsed by, or supported by GAF, Standard
Industries, or Keen Home. It relies on an undocumented cloud API that can change
or break at any time. Use at your own risk.

---

## License

Released under the [MIT License](LICENSE). © 2026 hitchin999.

<!-- Badge references -->
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[validate-badge]: https://github.com/hitchin999/GAFVentControl-HA/actions/workflows/validate.yml/badge.svg
[validate-url]: https://github.com/hitchin999/GAFVentControl-HA/actions/workflows/validate.yml
[hassfest-badge]: https://github.com/hitchin999/GAFVentControl-HA/actions/workflows/hassfest.yml/badge.svg
[hassfest-url]: https://github.com/hitchin999/GAFVentControl-HA/actions/workflows/hassfest.yml
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
