"""Fan platform for i-Vent Cloud ventilation groups."""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FAN_PRESETS,
    PRESET_TO_WORK_MODE,
    SPEED_TO_PERCENTAGE,
    WorkMode,
    percentage_to_speed,
)
from .coordinator import IVentCoordinator
from .entity import IVentGroupEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the fan entities for all groups."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(IVentFan(coordinator, group.id) for group in coordinator.groups)


class IVentFan(IVentGroupEntity, FanEntity):
    """Fan entity representing a ventilation group."""

    _attr_name = None
    _attr_icon = "mdi:fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes: ClassVar[list[str]] = list(FAN_PRESETS)

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"{group_id}_fan"

    @property
    def is_on(self) -> bool:
        """Return True if the group is not in IVentWorkOff."""
        return self.group is not None and self.group.remote.work_mode != WorkMode.OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if self.group is None:
            return None
        return SPEED_TO_PERCENTAGE.get(self.group.remote.remote_control_speed)

    @property
    def preset_mode(self) -> str | None:
        """Return the friendly preset matching the current work mode."""
        if self.group is None:
            return None
        return PRESET_TO_WORK_MODE.get(self.group.remote.work_mode)

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        """Turn the group on, optionally with a percentage or preset mode."""
        if preset_mode is not None:
            work_mode: str | None = FAN_PRESETS[preset_mode]
        elif self.is_on:
            work_mode = None
        else:
            work_mode = WorkMode.ON
        speed = percentage_to_speed(percentage) if percentage is not None else None
        await self.coordinator.async_set_remote(
            self._group_id, work_mode=work_mode, remote_control_speed=speed
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the group off (IVentWorkOff)."""
        await self.coordinator.async_set_remote(self._group_id, work_mode=WorkMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the work mode via a preset."""
        await self.coordinator.async_set_remote(self._group_id, work_mode=FAN_PRESETS[preset_mode])

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed (1-3) from a percentage."""
        work_mode = None if self.is_on else WorkMode.ON
        await self.coordinator.async_set_remote(
            self._group_id, remote_control_speed=percentage_to_speed(percentage), work_mode=work_mode
        )
