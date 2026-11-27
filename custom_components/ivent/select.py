"""Select platform for i-Vent Cloud."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LiveGroup
from .const import (
    BUZZER_MODE_OPTIONS,
    BYPASS_ROTATION_OPTIONS,
    CUSTOM_DAYS,
    DAY_PRESETS,
    DOMAIN,
    LED_MODE_OPTIONS,
    REMOTE_CONTROL_MODE_OPTIONS,
    SPECIAL_MODE_OPTIONS,
    WORK_MODE_OPTIONS,
)
from .coordinator import IVentCoordinator
from .entity import IVentGroupEntity


class IVentGroupSelect(IVentGroupEntity, SelectEntity):
    """Base select for group-level settings."""

    def __init__(
        self,
        coordinator: IVentCoordinator,
        group_id: int,
        *,
        key: str,
        translation_key: str,
        options_map: dict[str, Any],
        current_fn: Callable[[LiveGroup], str],
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"{group_id}_{key}"
        self._attr_translation_key = translation_key
        self._options_map = options_map
        self._attr_options = list(options_map)
        self._current_fn = current_fn
        if entity_category is not None:
            self._attr_entity_category = entity_category

    @property
    def current_option(self) -> str | None:
        """Return the friendly option matching the current API value."""
        if self.group is None:
            return None
        api_value = self._current_fn(self.group)
        for option, value in self._options_map.items():
            if value == api_value:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the API value for the selected friendly option."""
        await self._async_set_option(self._options_map[option])

    async def _async_set_option(self, api_value: str) -> None:
        raise NotImplementedError


class SpecialModeSelect(IVentGroupSelect):
    """Select for the IVentSpecialMode (Boost/Snooze/Night...)."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            group_id,
            key="special_mode",
            translation_key="special_mode",
            options_map=SPECIAL_MODE_OPTIONS,
            current_fn=lambda group: group.remote.special_mode,
        )

    async def _async_set_option(self, api_value: str) -> None:
        await self.coordinator.async_set_remote(self._group_id, special_mode=api_value)


class BypassRotationSelect(IVentGroupSelect):
    """Select for the bypass damper rotation direction."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            group_id,
            key="bypass_rotation",
            translation_key="bypass_rotation",
            options_map=BYPASS_ROTATION_OPTIONS,
            current_fn=lambda group: group.remote.bypass_rotation,
            entity_category=EntityCategory.CONFIG,
        )

    async def _async_set_option(self, api_value: str) -> None:
        await self.coordinator.async_set_remote(self._group_id, bypass_rotation=api_value)


class RemoteControlModeSelect(IVentGroupSelect):
    """Select for the remote control work mode (Normal/Bypass)."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            group_id,
            key="remote_control_mode",
            translation_key="remote_control_mode",
            options_map=REMOTE_CONTROL_MODE_OPTIONS,
            current_fn=lambda group: group.remote.remote_control_work_mode,
            entity_category=EntityCategory.CONFIG,
        )

    async def _async_set_option(self, api_value: str) -> None:
        await self.coordinator.async_set_remote(self._group_id, remote_control_work_mode=api_value)


class LedModeSelect(IVentGroupSelect):
    """Select for the group LED work mode."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            group_id,
            key="led_mode",
            translation_key="led_mode",
            options_map=LED_MODE_OPTIONS,
            current_fn=lambda group: group.led_work_mode,
            entity_category=EntityCategory.CONFIG,
        )

    async def _async_set_option(self, api_value: str) -> None:
        await self.coordinator.async_set_led_mode(self._group_id, api_value)


class BuzzerModeSelect(IVentGroupSelect):
    """Select for the group buzzer work mode."""

    def __init__(self, coordinator: IVentCoordinator, group_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            group_id,
            key="buzzer_mode",
            translation_key="buzzer_mode",
            options_map=BUZZER_MODE_OPTIONS,
            current_fn=lambda group: group.buzzer_work_mode,
            entity_category=EntityCategory.CONFIG,
        )

    async def _async_set_option(self, api_value: str) -> None:
        await self.coordinator.async_set_buzzer_mode(self._group_id, api_value)


class ScheduleSelect(IVentGroupEntity, SelectEntity):
    """Base select for a single schedule item."""

    def __init__(
        self,
        coordinator: IVentCoordinator,
        group_id: int,
        schedule_id: int,
        *,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize the schedule select."""
        super().__init__(coordinator, group_id)
        self._schedule_id = schedule_id
        self._attr_unique_id = f"{group_id}_schedule_{schedule_id}_{key}"
        self._attr_translation_key = translation_key

    @property
    def _item(self) -> dict[str, Any] | None:
        return self.coordinator.get_schedule_item(self._group_id, self._schedule_id)

    @property
    def available(self) -> bool:
        """Return True if the schedule item still exists."""
        return super().available and self._item is not None

    def _api_value_to_option(self, api_value: str, options_map: dict[str, Any]) -> str | None:
        for option, value in options_map.items():
            if value == api_value:
                return option
        return None


class ScheduleWorkModeSelect(ScheduleSelect):
    """Select the work mode a schedule switches to."""

    _attr_options: ClassVar[list[str]] = list(WORK_MODE_OPTIONS)

    def __init__(self, coordinator: IVentCoordinator, group_id: int, schedule_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator, group_id, schedule_id, key="work_mode", translation_key="schedule_work_mode"
        )

    @property
    def current_option(self) -> str | None:
        if self._item is None:
            return None
        return self._api_value_to_option(self._item["action"]["work_mode"], WORK_MODE_OPTIONS)

    async def async_select_option(self, option: str) -> None:
        """Set the schedule work mode."""
        await self.coordinator.async_update_schedule_item(
            self._group_id, self._schedule_id, work_mode=WORK_MODE_OPTIONS[option]
        )


class ScheduleSpecialModeSelect(ScheduleSelect):
    """Select the special mode a schedule switches to."""

    _attr_options: ClassVar[list[str]] = list(SPECIAL_MODE_OPTIONS)

    def __init__(self, coordinator: IVentCoordinator, group_id: int, schedule_id: int) -> None:
        """Initialize."""
        super().__init__(
            coordinator, group_id, schedule_id, key="special_mode", translation_key="schedule_special_mode"
        )

    @property
    def current_option(self) -> str | None:
        if self._item is None:
            return None
        return self._api_value_to_option(self._item["action"]["special_mode"], SPECIAL_MODE_OPTIONS)

    async def async_select_option(self, option: str) -> None:
        """Set the schedule special mode."""
        await self.coordinator.async_update_schedule_item(
            self._group_id, self._schedule_id, special_mode=SPECIAL_MODE_OPTIONS[option]
        )


class ScheduleDaysSelect(ScheduleSelect):
    """Select the days a schedule is active on."""

    _attr_options: ClassVar[list[str]] = [*list(DAY_PRESETS), CUSTOM_DAYS]

    def __init__(self, coordinator: IVentCoordinator, group_id: int, schedule_id: int) -> None:
        """Initialize."""
        super().__init__(coordinator, group_id, schedule_id, key="days", translation_key="schedule_days")

    @property
    def current_option(self) -> str | None:
        if self._item is None:
            return None
        days = self._item["repeat"]["days"]
        for option, value in DAY_PRESETS.items():
            if value == days:
                return option
        return CUSTOM_DAYS

    async def async_select_option(self, option: str) -> None:
        """Set the schedule days bitmask (Custom is read-only)."""
        if option == CUSTOM_DAYS:
            return
        await self.coordinator.async_update_schedule_item(
            self._group_id, self._schedule_id, days=DAY_PRESETS[option]
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all select entities."""
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []
    for group in coordinator.groups:
        entities.extend(
            [
                SpecialModeSelect(coordinator, group.id),
                BypassRotationSelect(coordinator, group.id),
                RemoteControlModeSelect(coordinator, group.id),
                LedModeSelect(coordinator, group.id),
                BuzzerModeSelect(coordinator, group.id),
            ]
        )
        group_schedules = coordinator.get_group_schedules(group.id)
        for item in (group_schedules or {}).get("schedules", []):
            schedule_id = item["meta"]["schedule_id"]
            entities.extend(
                [
                    ScheduleWorkModeSelect(coordinator, group.id, schedule_id),
                    ScheduleSpecialModeSelect(coordinator, group.id, schedule_id),
                    ScheduleDaysSelect(coordinator, group.id, schedule_id),
                ]
            )
    async_add_entities(entities)
