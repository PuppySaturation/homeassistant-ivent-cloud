"""Binary sensor platform for i-Vent Cloud."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IVentCoordinator
from .entity import IVentDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up connectivity binary sensors for all physical devices."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DeviceAliveBinarySensor(coordinator, device.mac_address)
        for group in coordinator.groups
        for device in group.devices
    )


class DeviceAliveBinarySensor(IVentDeviceEntity, BinarySensorEntity):
    """Connectivity (alive) state of a physical device."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "alive"

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_alive"

    @property
    def is_on(self) -> bool | None:
        """Return True if the device is alive."""
        return self.device.alive if self.device else None
