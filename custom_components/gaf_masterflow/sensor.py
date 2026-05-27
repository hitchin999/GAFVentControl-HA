"""Sensor platform for GAF MasterFlow.

Field-mapping notes (do not trust the API field names — they are misleading):

    deviceConfig.setTemperature   -> CURRENT temperature reading  (live)
    deviceConfig.setHumidity      -> CURRENT humidity reading     (live)
    deviceSettings.setTemperature -> TARGET temperature           (set-point)
    deviceSettings.setHumidity    -> TARGET humidity              (set-point)

These were confirmed against the app UI ("Current Conditions: 77°F / 34%"
matched ``deviceConfig.setTemperature: 77.0`` at the same moment).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GafCoordinator
from .entity import GafBaseEntity


def _settings(rec: dict[str, Any]) -> dict[str, Any]:
    """deviceSettings holds the target set-points & mode flags."""
    return rec.get("deviceSettings") or {}


def _config(rec: dict[str, Any]) -> dict[str, Any]:
    """deviceConfig holds the LIVE temperature & humidity readings."""
    return rec.get("deviceConfig") or {}


def _derive_mode(s: dict[str, Any]) -> str:
    if s.get("automaticMode"):
        return "automatic"
    if s.get("timerMode"):
        return "timer"
    if s.get("fanMode"):
        return "manual"   # the app labels fanMode as "Manual mode"
    return "off"


@dataclass(kw_only=True, frozen=True)
class GafSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_TYPES: tuple[GafSensorDescription, ...] = (
    # ---- LIVE readings (deviceConfig) ----
    GafSensorDescription(
        key="current_temperature",
        translation_key="current_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda d: _config(d).get("setTemperature"),
    ),
    GafSensorDescription(
        key="current_humidity",
        translation_key="current_humidity",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: _config(d).get("setHumidity"),
    ),
    # ---- Target set-points (deviceSettings) ----
    # ---- Diagnostic ----
    GafSensorDescription(
        key="signal_strength",
        translation_key="signal_strength",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("signalStrength"),
    ),
    GafSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("firmwareVersion"),
    ),
    GafSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("serialNumber"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GafCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[GafSensor] = []
    for device_id in coordinator.data or {}:
        for desc in SENSOR_TYPES:
            entities.append(GafSensor(coordinator, device_id, desc))
    async_add_entities(entities)


class GafSensor(GafBaseEntity, SensorEntity):
    entity_description: GafSensorDescription

    def __init__(
        self,
        coordinator: GafCoordinator,
        device_id: str,
        description: GafSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device_record)
