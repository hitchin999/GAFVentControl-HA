"""DataUpdateCoordinator for GAF MasterFlow devices."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GafApiClient, GafApiError, GafAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GafCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls deviceList then enriches each device with its detail payload."""

    def __init__(self, hass: HomeAssistant, client: GafApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.async_list_devices()
        except GafAuthError as err:
            raise UpdateFailed(f"auth failure: {err}") from err
        except GafApiError as err:
            raise UpdateFailed(f"api failure: {err}") from err

        _LOGGER.debug("deviceList: %s", devices)

        out: dict[str, dict[str, Any]] = {}
        for dev in devices:
            device_id = (
                dev.get("deviceId")
                or dev.get("device_id")
                or dev.get("id")
                or dev.get("serialNumber")
                or dev.get("serial_number")
            )
            if not device_id:
                _LOGGER.debug("Skipping device with no id: %s", dev)
                continue
            try:
                detail = await self.client.async_get_device(device_id)
            except GafApiError as err:
                _LOGGER.warning("detail fetch failed for %s: %s", device_id, err)
                detail = {}
            _LOGGER.debug("device detail %s: %s", device_id, detail)
            out[str(device_id)] = {**dev, **detail}

        return out
