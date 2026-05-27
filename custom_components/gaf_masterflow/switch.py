"""Switch platform for GAF MasterFlow.

Three independent-looking switches that actually form a mutually-exclusive
set (Automatic / Timer / Manual). Turning a switch ON forces the OTHER two
flags to false in the same POST so the app and the device stay in sync.
The cleaner UX for this is the ``Mode`` select entity (see select.py); the
switches are kept for dashboard / automation convenience.

Write body shape:
    {automaticMode, desiredTemp, desiredHumidity,
     timerMode, timerValue, fanMode}    -- all six fields, JSON ints
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GafApiError
from .const import DOMAIN, MODE_FLAGS
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


def _settings(coordinator: GafCoordinator, device_id: str) -> dict[str, Any]:
    return (coordinator.data.get(device_id) or {}).get("deviceSettings") or {}


def _build_mode_body(
    coordinator: GafCoordinator, device_id: str, *, flag: str, value: bool
) -> dict[str, Any]:
    """Return the full settings body with mode-flag mutex applied.

    If ``value`` is True, the other two mode flags are forced to False.
    If False, only the requested flag is cleared; the others keep their
    current values (so turning off the active mode doesn't accidentally
    activate another).
    """
    s = _settings(coordinator, device_id)
    # Start with all three flags carried forward
    flags: dict[str, bool] = {f: bool(s.get(f)) for f in MODE_FLAGS}
    if value:
        # Mutex: clear the other two
        for f in MODE_FLAGS:
            flags[f] = (f == flag)
    else:
        flags[flag] = False
    return {
        "automaticMode": flags["automaticMode"],
        "desiredTemp": _to_int(s.get("setTemperature")),
        "desiredHumidity": _to_int(s.get("setHumidity")),
        "timerMode": flags["timerMode"],
        "timerValue": _to_int(s.get("timerValue"), default=30),
        "fanMode": flags["fanMode"],
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GafCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[GafBaseEntity] = []
    for device_id in coordinator.data or {}:
        for flag in MODE_FLAGS:
            entities.append(GafModeFlagSwitch(coordinator, device_id, flag))
    async_add_entities(entities)


_FLAG_META = {
    "automaticMode": ("automatic_mode", "mdi:autorenew"),
    "timerMode": ("timer_mode", "mdi:timer"),
    "fanMode": ("fan_mode", "mdi:fan"),
}


class GafModeFlagSwitch(GafBaseEntity, SwitchEntity):
    """Single switch that flips one mode flag (with mutex on turn-on)."""

    def __init__(
        self, coordinator: GafCoordinator, device_id: str, flag: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._flag = flag
        snake, icon = _FLAG_META[flag]
        self._attr_translation_key = snake
        self._attr_icon = icon
        self._attr_unique_id = f"{device_id}_{snake}_switch"

    @property
    def is_on(self) -> bool | None:
        val = _settings(self.coordinator, self._device_id).get(self._flag)
        return None if val is None else bool(val)

    async def _send(self, new_value: bool) -> None:
        body = _build_mode_body(
            self.coordinator, self._device_id, flag=self._flag, value=new_value
        )
        _LOGGER.debug(
            "Set %s=%s on device %s -> body=%s",
            self._flag, new_value, self._device_id, body,
        )
        try:
            await self.coordinator.client.async_update_device_settings(
                self._device_id, body
            )
        except GafApiError as err:
            raise RuntimeError(
                f"failed to set {self._flag}={new_value}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **_: Any) -> None:
        await self._send(True)

    async def async_turn_off(self, **_: Any) -> None:
        await self._send(False)
