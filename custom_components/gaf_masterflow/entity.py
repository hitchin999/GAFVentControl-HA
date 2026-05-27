"""Shared base entity for GAF MasterFlow devices."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import GafCoordinator


class GafBaseEntity(CoordinatorEntity[GafCoordinator]):
    """Common parent for every entity attached to a single device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GafCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_record(self) -> dict[str, Any]:
        """Return the current snapshot for this device, or {} if missing."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self._device_id in (self.coordinator.data or {})
        )

    @property
    def device_info(self) -> DeviceInfo:
        rec = self.device_record
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            model="MasterFlow Smart Attic Fan",
            name=rec.get("deviceName") or f"MasterFlow {self._device_id}",
            sw_version=(str(rec.get("firmwareVersion")) if rec.get("firmwareVersion") else None),
            serial_number=(str(rec.get("serialNumber")) if rec.get("serialNumber") else None),
        )
