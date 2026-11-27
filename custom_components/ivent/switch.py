"""Switch platform for i-Vent Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IVentCoordinator
from .entity import IVentDeviceEntity, IVentGroupEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all switch entities."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []
    for group in coordinator.groups:
        entities.append(SchedulesEnabledSwitch(coordinator, group.id))
        group_schedules = coordinator.get_group_schedules(group.id)
        for item in (group_schedules or {}).get("schedules", []):
            entities.append(ScheduleItemEnabledSwitch(coordinator, group.id, item["meta"]["schedule_id"]))
        for device in group.devices:
            entities.append(ReverseFlowSwitch(coordinator, device.mac_address))
    async_add_entities(entities)


class SchedulesEnabledSwitch(IVentGroupEntity, SwitchEntity):
    """Switch to enable/disable the schedules feature of a group."""

    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "schedules_enabled"

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"{group_id}_schedules_enabled"

    @property
    def is_on(self) -> bool | None:
        """Return True if schedules are enabled for the group."""
        return self.group.enable_schedule if self.group else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable schedules."""
        await self.coordinator.async_set_schedules_enabled(self._group_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable schedules."""
        await self.coordinator.async_set_schedules_enabled(self._group_id, False)


class ScheduleItemEnabledSwitch(IVentGroupEntity, SwitchEntity):
    """Switch to enable/disable a single schedule item."""

    _attr_icon = "mdi:calendar-check"
    _attr_translation_key = "schedule_item_enabled"

    def __init__(self, coordinator: IVentCoordinator, group_id: int, schedule_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, group_id)
        self._schedule_id = schedule_id
        self._attr_unique_id = f"{group_id}_schedule_{schedule_id}_enabled"

    @property
    def _item(self) -> dict[str, Any] | None:
        return self.coordinator.get_schedule_item(self._group_id, self._schedule_id)

    @property
    def available(self) -> bool:
        """Return True if the schedule item still exists."""
        return super().available and self._item is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if the schedule item is enabled."""
        return self._item["header"]["schedule_item_enabled"] if self._item else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule item."""
        await self.coordinator.async_update_schedule_item(self._group_id, self._schedule_id, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule item."""
        await self.coordinator.async_update_schedule_item(self._group_id, self._schedule_id, enabled=False)


class ReverseFlowSwitch(IVentDeviceEntity, SwitchEntity):
    """Switch to invert the fan direction of a device."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:swap-horizontal"
    _attr_translation_key = "reverse_flow"

    def __init__(self, coordinator: IVentCoordinator, mac: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_reverse_flow"

    @property
    def is_on(self) -> bool | None:
        """Return True if the fan direction is inverted."""
        return self.device.reverse_flow if self.device else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Invert the fan direction."""
        await self.coordinator.async_set_device_reverse_flow(self._mac, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Restore the fan direction."""
        await self.coordinator.async_set_device_reverse_flow(self._mac, False)
