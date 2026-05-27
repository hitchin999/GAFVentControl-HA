"""Number platform for GAF MasterFlow.

Provides settable controls that mirror the app's sliders:

* Target temperature  – 90 to 120 °F, 1 °F step
* Target humidity     – 30 to 80 %,    1 %  step
* Timer value         – 30 to 360 min, 30-min step (max 6 hours)

Set-temperature/-humidity writes use the app's 3-field "Save Auto Settings"
body shape: ``{automaticMode, desiredTemp, desiredHumidity}``. This updates
the set-points without changing the active mode.

Timer-value writes use the 2-field "Save Timer Settings" shape:
``{timerMode, timerValue}``.

All numeric body fields MUST be JSON integers — the cloud's Jackson layer
rejects floats with HTTP 417 / statusCode 4444.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GafApiError
from .const import DOMAIN
from .coordinator import GafCoordinator
from .entity import GafBaseEntity

_LOGGER = logging.getLogger(__name__)

# App-observed ranges (from the "Set Temperature/Humidity" and timer dialogs)
TEMP_MIN, TEMP_MAX, TEMP_STEP = 90, 120, 1
HUM_MIN, HUM_MAX, HUM_STEP = 30, 80, 1
TIMER_MIN, TIMER_MAX, TIMER_STEP = 30, 360, 30


def _settings(coordinator: GafCoordinator, device_id: str) -> dict[str, Any]:
    return (coordinator.data.get(device_id) or {}).get("deviceSettings") or {}


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
    entities: list[GafBaseEntity] = []
    for device_id in coordinator.data or {}:
        entities.append(GafTargetTemperatureNumber(coordinator, device_id))
        entities.append(GafTargetHumidityNumber(coordinator, device_id))
        entities.append(GafTimerValueNumber(coordinator, device_id))
    async_add_entities(entities)


# ---------------------------------------------------------------------------


class _GafNumberBase(GafBaseEntity, NumberEntity):
    """Shared helpers; subclasses implement native_value + async_set_native_value."""

    _attr_mode = NumberMode.SLIDER

    async def _post(self, body: dict[str, Any]) -> None:
        _LOGGER.debug("Number write for %s: %s", self._device_id, body)
        try:
            await self.coordinator.client.async_update_device_settings(
                self._device_id, body
            )
        except GafApiError as err:
            raise RuntimeError(
                f"failed to update {type(self).__name__}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()


class GafTargetTemperatureNumber(_GafNumberBase):
    """Target temperature slider (90–120 °F, 1 °F step)."""

    _attr_translation_key = "target_temperature"
    _attr_icon = "mdi:thermostat"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_native_min_value = float(TEMP_MIN)
    _attr_native_max_value = float(TEMP_MAX)
    _attr_native_step = float(TEMP_STEP)

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_target_temperature_number"

    @property
    def native_value(self) -> float | None:
        v = _settings(self.coordinator, self._device_id).get("setTemperature")
        return None if v is None else float(v)

    async def async_set_native_value(self, value: float) -> None:
        s = _settings(self.coordinator, self._device_id)
        await self._post({
            "automaticMode": bool(s.get("automaticMode")),
            "desiredTemp": _to_int(value),
            "desiredHumidity": _to_int(s.get("setHumidity")),
        })


class GafTargetHumidityNumber(_GafNumberBase):
    """Target humidity slider (30–80 %, 1 % step)."""

    _attr_translation_key = "target_humidity"
    _attr_icon = "mdi:water-percent-alert"
    _attr_device_class = NumberDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = float(HUM_MIN)
    _attr_native_max_value = float(HUM_MAX)
    _attr_native_step = float(HUM_STEP)

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_target_humidity_number"

    @property
    def native_value(self) -> float | None:
        v = _settings(self.coordinator, self._device_id).get("setHumidity")
        return None if v is None else float(v)

    async def async_set_native_value(self, value: float) -> None:
        s = _settings(self.coordinator, self._device_id)
        await self._post({
            "automaticMode": bool(s.get("automaticMode")),
            "desiredTemp": _to_int(s.get("setTemperature")),
            "desiredHumidity": _to_int(value),
        })


class GafTimerValueNumber(_GafNumberBase):
    """Timer duration slider (30–360 min, 30-min step)."""

    _attr_translation_key = "timer_value"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = float(TIMER_MIN)
    _attr_native_max_value = float(TIMER_MAX)
    _attr_native_step = float(TIMER_STEP)

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_timer_value_number"

    @property
    def native_value(self) -> float | None:
        v = _settings(self.coordinator, self._device_id).get("timerValue")
        return None if v is None else float(v)

    async def async_set_native_value(self, value: float) -> None:
        s = _settings(self.coordinator, self._device_id)
        # Snap to nearest 30-min step in case HA's slider sends something else
        snapped = max(TIMER_MIN, min(TIMER_MAX, int(round(value / 30)) * 30))
        await self._post({
            "timerMode": bool(s.get("timerMode")),
            "timerValue": snapped,
        })
