"""Sensor platform for i-Vent Cloud."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SpecialMode
from .coordinator import IVentCoordinator
from .entity import IVentDeviceEntity, IVentGroupEntity, IVentLocationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all sensor entities."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [NetworkHashSensor(coordinator)]
    for group in coordinator.groups:
        entities.append(SpecialModeEndsAtSensor(coordinator, group.id))
        for device in group.devices:
            entities.extend(
                [
                    DeviceRssiSensor(coordinator, device.mac_address),
                    FirmwareVersionSensor(coordinator, device.mac_address),
                    StatusEspSensor(coordinator, device.mac_address),
                ]
            )
    async_add_entities(entities)


class NetworkHashSensor(IVentLocationEntity, SensorEntity):
    """Diagnostic sensor for the network hash (changes when the network state changes)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:hash"
    _attr_translation_key = "network_hash"

    def __init__(self, coordinator: IVentCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"location_{coordinator.loc_id}_network_hash"

    @property
    def native_value(self) -> int | None:
        """Return the network hash."""
        return self.coordinator.data.info.network_hash


class SpecialModeEndsAtSensor(IVentGroupEntity, SensorEntity):
    """Timestamp sensor for when the current special mode ends."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "special_mode_ends_at"

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"{group_id}_special_mode_ends_at"

    @property
    def native_value(self) -> datetime | None:
        """Return when the special mode ends, if a special mode is active."""
        if self.group is None:
            return None
        remote = self.group.remote
        if remote.special_mode == SpecialMode.OFF or not remote.special_mode_ends_at:
            return None
        return datetime.fromtimestamp(remote.special_mode_ends_at, tz=UTC)


class DeviceRssiSensor(IVentDeviceEntity, SensorEntity):
    """Signal strength of a physical device."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "rssi"

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_rssi"

    @property
    def native_value(self) -> int | None:
        """Return the RSSI in dBm."""
        return self.device.rssi if self.device else None


class FirmwareVersionSensor(IVentDeviceEntity, SensorEntity):
    """Firmware version of a physical device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:package-variant"
    _attr_translation_key = "firmware_version"

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_firmware_version"

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return str(self.device.firmware_version) if self.device else None


class StatusEspSensor(IVentDeviceEntity, SensorEntity):
    """Raw ESP status code of a physical device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:chip"
    _attr_translation_key = "status_esp"

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_status_esp"

    @property
    def native_value(self) -> int | None:
        """Return the ESP status code."""
        return self.device.status_esp if self.device else None
