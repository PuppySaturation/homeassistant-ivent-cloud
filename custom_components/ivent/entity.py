"""Base entity classes for the i-Vent Cloud integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import LiveDevice, LiveGroup
from .const import DOMAIN, MANUFACTURER
from .coordinator import IVentCoordinator


def location_identifier(loc_id: int) -> str:
    """Return the device registry identifier of a location (hub) device."""
    return f"location_{loc_id}"


class IVentEntity(CoordinatorEntity[IVentCoordinator]):
    """Base class for all i-Vent entities."""

    _attr_has_entity_name = True


class IVentLocationEntity(IVentEntity):
    """Entity attached to the location (hub) device."""

    def __init__(self, coordinator: IVentCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location_identifier(coordinator.loc_id))},
            name=f"i-Vent location {coordinator.loc_id}",
            manufacturer=MANUFACTURER,
        )


class IVentGroupEntity(IVentEntity):
    """Entity attached to a ventilation group device."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._group_id = group_id

    @property
    def group(self) -> LiveGroup | None:
        """Return the current group data."""
        return self.coordinator.get_group(self._group_id)

    @property
    def available(self) -> bool:
        """Return True if the group still exists and the coordinator is up."""
        return super().available and self.group is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the group."""
        group = self.group
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._group_id))},
            name=group.name if group else str(self._group_id),
            manufacturer=MANUFACTURER,
            model="Ventilation group",
            via_device=(DOMAIN, location_identifier(self.coordinator.loc_id)),
        )


class IVentDeviceEntity(IVentEntity):
    """Entity attached to a physical device (MAC)."""

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._mac = mac

    @property
    def device(self) -> LiveDevice | None:
        """Return the current device data."""
        found = self.coordinator.get_device(self._mac)
        return found[1] if found else None

    @property
    def group(self) -> LiveGroup | None:
        """Return the group the device belongs to."""
        found = self.coordinator.get_device(self._mac)
        return found[0] if found else None

    @property
    def available(self) -> bool:
        """Return True if the device still exists and the coordinator is up."""
        return super().available and self.device is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the physical device."""
        device = self.device
        group = self.group
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=device.device_name if device else self._mac,
            manufacturer=MANUFACTURER,
            model="Ventilation device",
            sw_version=str(device.firmware_version) if device else None,
            via_device=(DOMAIN, str(group.id)) if group else None,
        )
