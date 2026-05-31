"""Binary sensor platform for GAF MasterFlow."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GafCoordinator
from .entity import GafBaseEntity


def _settings(rec: dict[str, Any]) -> dict[str, Any]:
    return rec.get("deviceSettings") or {}


def _config(rec: dict[str, Any]) -> dict[str, Any]:
    return rec.get("deviceConfig") or {}


def _is_running(d: dict[str, Any]) -> bool | None:
    """Compute whether the attic fan is currently blowing.

    The cloud API doesn't expose this directly, so we infer it:

    * Manual mode ON  -> always running
    * Timer mode  ON  -> running (the device clears the flag when the timer
                          expires, so timerMode=true implies it's still active)
    * Automatic mode  -> running if current temp >= activation temp, OR
                         (humidity monitor on AND current humidity >= activation humidity)
    * Otherwise       -> off

    Returns None when settings are missing.
    """
    s = _settings(d)
    if not s:
        return None
    if s.get("fanMode"):
        return True
    if s.get("timerMode"):
        return True
    if s.get("automaticMode"):
        cfg = _config(d)
        cur_t = cfg.get("setTemperature")           # live temperature (°F)
        cur_h = cfg.get("setHumidity")              # live humidity (%)
        act_t = s.get("setTemperature")             # activation temperature
        act_h = s.get("setHumidity")                # activation humidity
        try:
            if cur_t is not None and act_t is not None and float(cur_t) >= float(act_t):
                return True
        except (TypeError, ValueError):
            pass
        if s.get("humidityMonitor"):
            try:
                if cur_h is not None and act_h is not None and float(cur_h) >= float(act_h):
                    return True
            except (TypeError, ValueError):
                pass
        return False
    return False


@dataclass(kw_only=True, frozen=True)
class GafBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_TYPES: tuple[GafBinaryDescription, ...] = (
    GafBinaryDescription(
        key="running",
        translation_key="running",
        icon="mdi:fan",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_is_running,
    ),
    GafBinaryDescription(
        key="verified",
        translation_key="verified",
        icon="mdi:check-decagram",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.get("isVerified"),
    ),
    GafBinaryDescription(
        key="ota_in_progress",
        translation_key="ota_in_progress",
        icon="mdi:cloud-download",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("otaInProgress"),
    ),
    GafBinaryDescription(
        key="automatic_mode",
        translation_key="automatic_mode",
        icon="mdi:autorenew",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: _settings(d).get("automaticMode"),
    ),
    GafBinaryDescription(
        key="timer_mode",
        translation_key="timer_mode",
        icon="mdi:timer",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: _settings(d).get("timerMode"),
    ),
    GafBinaryDescription(
        key="fan_mode",
        translation_key="fan_mode",
        icon="mdi:fan",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: _settings(d).get("fanMode"),
    ),
    GafBinaryDescription(
        key="humidity_monitor",
        translation_key="humidity_monitor",
        icon="mdi:water-percent",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: _settings(d).get("humidityMonitor"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GafCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[GafBinarySensor] = []
    for device_id in coordinator.data or {}:
        for desc in BINARY_SENSOR_TYPES:
            entities.append(GafBinarySensor(coordinator, device_id, desc))
    async_add_entities(entities)


class GafBinarySensor(GafBaseEntity, BinarySensorEntity):
    entity_description: GafBinaryDescription

    def __init__(
        self,
        coordinator: GafCoordinator,
        device_id: str,
        description: GafBinaryDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        val = self.entity_description.value_fn(self.device_record)
        if val is None:
            return None
        return bool(val)
