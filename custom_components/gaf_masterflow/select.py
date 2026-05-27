"""Select platform for GAF MasterFlow.

A single 'Mode' select entity that mirrors the device's actual semantics:
the three operating-mode flags are mutually exclusive. Options:

    off       -> all three flags false
    automatic -> automaticMode=true,  timer/fan=false
    timer     -> timerMode=true,      automatic/fan=false
    manual    -> fanMode=true,        automatic/timer=false  (app: "Manual mode")
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GafApiError
from .const import DOMAIN
from .coordinator import GafCoordinator
from .entity import GafBaseEntity

_LOGGER = logging.getLogger(__name__)

OPTION_OFF = "off"
OPTION_AUTOMATIC = "automatic"
OPTION_TIMER = "timer"
OPTION_MANUAL = "manual"
OPTIONS: list[str] = [OPTION_OFF, OPTION_AUTOMATIC, OPTION_TIMER, OPTION_MANUAL]

# Maps option -> (automaticMode, timerMode, fanMode)
_OPTION_TO_FLAGS: dict[str, tuple[bool, bool, bool]] = {
    OPTION_OFF: (False, False, False),
    OPTION_AUTOMATIC: (True, False, False),
    OPTION_TIMER: (False, True, False),
    OPTION_MANUAL: (False, False, True),
}


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
    async_add_entities(
        GafModeSelect(coordinator, device_id)
        for device_id in (coordinator.data or {})
    )


class GafModeSelect(GafBaseEntity, SelectEntity):
    """Mode dropdown — one of off / automatic / timer / manual."""

    _attr_translation_key = "mode"
    _attr_icon = "mdi:tune-vertical"
    _attr_options = OPTIONS

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_mode_select"

    @property
    def current_option(self) -> str | None:
        s = (self.device_record.get("deviceSettings") or {})
        if s.get("automaticMode"):
            return OPTION_AUTOMATIC
        if s.get("timerMode"):
            return OPTION_TIMER
        if s.get("fanMode"):
            return OPTION_MANUAL
        return OPTION_OFF

    async def async_select_option(self, option: str) -> None:
        if option not in _OPTION_TO_FLAGS:
            raise ValueError(f"unknown mode: {option}")
        auto, timer, fan = _OPTION_TO_FLAGS[option]
        s = (self.device_record.get("deviceSettings") or {})
        body = {
            "automaticMode": auto,
            "desiredTemp": _to_int(s.get("setTemperature")),
            "desiredHumidity": _to_int(s.get("setHumidity")),
            "timerMode": timer,
            "timerValue": _to_int(s.get("timerValue"), default=30),
            "fanMode": fan,
        }
        _LOGGER.debug("Mode select %s -> body=%s", option, body)
        try:
            await self.coordinator.client.async_update_device_settings(
                self._device_id, body
            )
        except GafApiError as err:
            raise RuntimeError(f"failed to set mode={option}: {err}") from err
        await self.coordinator.async_request_refresh()
