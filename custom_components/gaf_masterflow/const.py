"""Constants for the GAF MasterFlow Vent Control integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "gaf_masterflow"
MANUFACTURER = "GAF / Keen Home"

# Values extracted from the Android app's bundled JS (v1.0.9).
AWS_BASE_URL: str = "https://gaf-coreservices.aurai.io/cognito/"
GAF_SERVICE_URL: str = "https://gaf.keenhome.io/gaf/"
USER_POOL_ID: str = "us-east-2_F6aHzg32w"

DEFAULT_USER_ROLE: str = "contractor"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USER_ROLE = "user_role"

# Halved from 60s to keep HA reasonably fresh after app-side changes.
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# The three mutually-exclusive operating-mode flags in deviceSettings.
MODE_FLAGS: tuple[str, ...] = ("automaticMode", "timerMode", "fanMode")
