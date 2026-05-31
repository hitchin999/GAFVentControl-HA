"""Async API client for the GAF MasterFlow / Keen Home cloud.

Endpoints reverse-engineered from "Vent Control" v1.0.9 Android app.
Two hosts:
  * https://gaf-coreservices.aurai.io/cognito/   -> AWS Cognito auth proxy
  * https://gaf.keenhome.io/gaf/                 -> Device & config service

Authenticated requests send the Cognito idToken as the literal
``Authorization`` header (no ``Bearer `` prefix).
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from .const import AWS_BASE_URL, DEFAULT_USER_ROLE, GAF_SERVICE_URL, USER_POOL_ID

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=20)


class GafAuthError(Exception):
    """Raised when credentials are rejected (HTTP 4xx, missing idToken)."""


class GafApiError(Exception):
    """Raised for non-credential failures (network, server, transient)."""


class GafApiClient:
    """Thin async wrapper around the Keen Home/GAF cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        user_role: str = DEFAULT_USER_ROLE,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._user_role = user_role
        self._id_token: str | None = None

    async def async_login(self) -> str:
        encoded_pw = base64.b64encode(self._password.encode("utf-8")).decode("ascii")
        payload = {
            "userName": self._username.strip(),
            "password": encoded_pw,
            "userPoolId": USER_POOL_ID,
            "userRole": self._user_role,
        }
        try:
            async with self._session.post(
                AWS_BASE_URL + "login", json=payload, timeout=_TIMEOUT,
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 500:
                    # Server-side glitch — transient, let HA retry.
                    raise GafApiError(
                        f"login server error: HTTP {resp.status} "
                        f"{(data or {}).get('statusInfo', '')}"
                    )
                if resp.status != 200:
                    # 4xx = credentials rejected (or malformed request).
                    raise GafAuthError(
                        f"login failed: {resp.status} "
                        f"{(data or {}).get('statusInfo', '')}"
                    )
        except (ClientError, TimeoutError) as err:
            # DNS, timeout, connection refused, etc. — NOT a credentials issue.
            # Raise GafApiError so __init__.py maps it to ConfigEntryNotReady,
            # which lets HA auto-retry with exponential backoff instead of
            # marking the entry as needing re-auth.
            raise GafApiError(
                f"network error during login: {type(err).__name__}: {err}"
            ) from err

        token = ((data or {}).get("responseData") or {}).get("idToken")
        if not token:
            raise GafAuthError("login response did not contain an idToken")
        self._id_token = token
        return token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> Any:
        token = self._id_token or await self.async_login()
        headers = {"Authorization": token}
        try:
            async with self._session.request(
                method, url,
                headers=headers, json=json_body, params=params, timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403) and _retry:
                    _LOGGER.debug("auth rejected; refreshing token and retrying")
                    self._id_token = None
                    await self.async_login()
                    return await self._request(
                        method, url, json_body=json_body, params=params, _retry=False
                    )
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise GafApiError(f"{method} {url} -> HTTP {resp.status}: {data}")
                return data
        except ClientResponseError as err:
            raise GafApiError(str(err)) from err
        except (ClientError, TimeoutError) as err:
            raise GafApiError(f"network error: {type(err).__name__}: {err}") from err

    # ---------- device API ---------------------------------------------

    async def async_list_devices(self) -> list[dict[str, Any]]:
        data = await self._request("GET", GAF_SERVICE_URL + "device/deviceList")
        rd = (data or {}).get("responseData")
        if isinstance(rd, list):
            return rd
        if isinstance(rd, dict) and "devices" in rd:
            return rd["devices"]
        _LOGGER.debug("Unexpected deviceList shape: %s", data)
        return []

    async def async_get_device(self, device_id: str | int) -> dict[str, Any]:
        data = await self._request(
            "GET", GAF_SERVICE_URL + "device",
            params={"deviceId": device_id},
        )
        return (data or {}).get("responseData") or {}

    async def async_update_device_settings(
        self, device_id: str | int, body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /gaf/deviceMode/{deviceId}.

        IMPORTANT: the write body uses different field names than the read
        response. Acceptable fields (from the app):
            automaticMode  (bool)
            timerMode      (bool)
            fanMode        (bool)
            desiredTemp    (float, °F)   - NOTE: not 'setTemperature'
            desiredHumidity(float, %)    - NOTE: not 'setHumidity'
            timerValue     (int, minutes)

        Sending unknown fields (e.g. ``setTemperature``, ``deviceSettingsId``,
        ``humidityMonitor``) causes the server to return statusCode 4444
        (HTTP 417).
        """
        url = f"{GAF_SERVICE_URL}deviceMode/{device_id}"
        return await self._request("POST", url, json_body=body)

    async def async_get_firmware_info(self, device_id: str | int) -> dict[str, Any]:
        """GET /gaf/fw/fwInfo?deviceId=X.

        Returns at least:
            current_fw_version, latest_fw_version_available,
            do_update_required, otaInProgress.
        """
        data = await self._request(
            "GET", GAF_SERVICE_URL + "fw/fwInfo",
            params={"deviceId": device_id},
        )
        return (data or {}).get("responseData") or {}

    async def async_trigger_firmware_update(
        self, device_id: str | int
    ) -> dict[str, Any]:
        """Trigger an OTA firmware update.

        Workflow:
          1. GET fwInfo to discover ``latest_fw_version_available``.
          2. PUT /gaf/fw/fwUpdate?device_id=X&fw_version=Y.
        Raises GafApiError if no newer version is available.
        """
        info = await self.async_get_firmware_info(device_id)
        latest = info.get("latest_fw_version_available")
        current = info.get("current_fw_version")
        if not latest:
            raise GafApiError(
                f"fwInfo did not report latest_fw_version_available: {info}"
            )
        if latest == current and not info.get("do_update_required"):
            raise GafApiError(
                f"already on latest firmware ({current}); nothing to update"
            )
        return await self._request(
            "PUT", GAF_SERVICE_URL + "fw/fwUpdate",
            params={"device_id": device_id, "fw_version": latest},
            json_body={},
        )

    async def async_rename_device(
        self, device_id: str | int, name: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST", GAF_SERVICE_URL + "device/rename",
            params={"deviceId": device_id},
            json_body={"deviceName": name},
        )

    async def async_update_global_config(
        self, target_temp: float, target_humidity: float
    ) -> dict[str, Any]:
        return await self._request(
            "PUT", GAF_SERVICE_URL + "device/updateGlobalConfig",
            params={"humid": target_humidity, "temp": target_temp},
        )
