"""Button platform for GAF MasterFlow."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GafApiError
from .const import DOMAIN
from .coordinator import GafCoordinator
from .entity import GafBaseEntity

_LOGGER = logging.getLogger(__name__)


def _to_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GafCoordinator = hass.data[DOMAIN][entry.entry_id]
    buttons: list[GafBaseEntity] = []
    for device_id in coordinator.data or {}:
        buttons.append(GafAllOffButton(coordinator, device_id))
        buttons.append(GafRefreshButton(coordinator, device_id))
        buttons.append(GafFirmwareButton(coordinator, device_id))
    async_add_entities(buttons)


class GafAllOffButton(GafBaseEntity, ButtonEntity):
    """One-press 'turn everything off' — clears all three mode flags."""

    _attr_translation_key = "all_off"
    _attr_icon = "mdi:power-off"

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_all_off"

    async def async_press(self) -> None:
        s = (self.coordinator.data.get(self._device_id) or {}).get(
            "deviceSettings"
        ) or {}
        body = {
            "automaticMode": False,
            "desiredTemp": _to_int(s.get("setTemperature")),
            "desiredHumidity": _to_int(s.get("setHumidity")),
            "timerMode": False,
            "timerValue": _to_int(s.get("timerValue"), default=30),
            "fanMode": False,
        }
        _LOGGER.debug("All-off body for %s: %s", self._device_id, body)
        try:
            await self.coordinator.client.async_update_device_settings(
                self._device_id, body
            )
        except GafApiError as err:
            raise RuntimeError(f"failed to turn off: {err}") from err
        await self.coordinator.async_request_refresh()


class GafRefreshButton(GafBaseEntity, ButtonEntity):
    """Force an immediate refresh from the cloud (bypass the poll interval)."""

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()


class GafFirmwareButton(GafBaseEntity, ButtonEntity):
    """Check for and trigger a firmware update."""

    _attr_translation_key = "firmware_update"
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.UPDATE

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_firmware_update"

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.async_trigger_firmware_update(
                self._device_id
            )
        except GafApiError as err:
            raise RuntimeError(f"firmware update: {err}") from err
        await self.coordinator.async_request_refresh()
