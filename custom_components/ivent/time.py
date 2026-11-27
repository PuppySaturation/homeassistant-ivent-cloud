"""Time platform for i-Vent Cloud schedule items."""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IVentCoordinator
from .entity import IVentGroupEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a time entity per schedule item."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[TimeEntity] = []
    for group in coordinator.groups:
        group_schedules = coordinator.get_group_schedules(group.id)
        for item in (group_schedules or {}).get("schedules", []):
            entities.append(ScheduleTime(coordinator, group.id, item["meta"]["schedule_id"]))
    async_add_entities(entities)


class ScheduleTime(IVentGroupEntity, TimeEntity):
    """Time entity for the hour/minute a schedule fires at."""

    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "schedule_time"

    def __init__(self, coordinator: IVentCoordinator, group_id: int, schedule_id: int) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator, group_id)
        self._schedule_id = schedule_id
        self._attr_unique_id = f"{group_id}_schedule_{schedule_id}_time"

    @property
    def _item(self) -> dict[str, Any] | None:
        return self.coordinator.get_schedule_item(self._group_id, self._schedule_id)

    @property
    def available(self) -> bool:
        """Return True if the schedule item still exists."""
        return super().available and self._item is not None

    @property
    def native_value(self) -> time | None:
        """Return the scheduled time."""
        if self._item is None:
            return None
        repeat = self._item["repeat"]
        return time(hour=repeat["hour"], minute=repeat["minute"])

    async def async_set_value(self, value: time) -> None:
        """Set the scheduled time."""
        await self.coordinator.async_update_schedule_item(
            self._group_id, self._schedule_id, hour=value.hour, minute=value.minute
        )
