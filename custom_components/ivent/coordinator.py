"""Data update coordinator for the i-Vent Cloud integration."""

from __future__ import annotations

import logging
import random
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IVentApiClient, IVentAuthError, IVentError, LiveDevice, LiveGroup, LiveInfo
from .const import CONF_LOC_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class IVentData:
    """Data polled from the cloud: system info plus raw schedule entries."""

    info: LiveInfo
    schedules: list[dict[str, Any]]


class IVentCoordinator(DataUpdateCoordinator[IVentData]):
    """Coordinator polling the i-Vent cloud for one location."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: IVentApiClient) -> None:
        """Initialize the coordinator."""
        scan_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_LOC_ID]}",
            update_interval=scan_interval,
            config_entry=entry,
        )
        self.api = api
        self.loc_id: int = entry.data[CONF_LOC_ID]

    async def _async_update_data(self) -> IVentData:
        """Fetch info and schedules from the cloud."""
        try:
            info = await self.api.async_get_info()
            schedules = await self.api.async_get_schedules()
        except IVentAuthError as err:
            raise ConfigEntryAuthFailed from err
        except IVentError as err:
            raise UpdateFailed(f"Error communicating with i-Vent cloud: {err}") from err
        return IVentData(info=info, schedules=schedules)

    @property
    def groups(self) -> list[LiveGroup]:
        """Return all groups of the location."""
        return self.data.info.groups

    def get_group(self, group_id: int) -> LiveGroup | None:
        """Return a group by id."""
        return next((g for g in self.data.info.groups if g.id == group_id), None)

    def get_device(self, mac: str) -> tuple[LiveGroup, LiveDevice] | None:
        """Return the group and device for a MAC address."""
        for group in self.data.info.groups:
            for device in group.devices:
                if device.mac_address == mac:
                    return group, device
        return None

    def get_group_schedules(self, group_id: int) -> dict[str, Any] | None:
        """Return the raw LiveGroupSchedule dict for a group."""
        return next((s for s in self.data.schedules if s.get("id") == group_id), None)

    def get_schedule_item(self, group_id: int, schedule_id: int) -> dict[str, Any] | None:
        """Return one raw ScheduleItem of a group."""
        group_schedules = self.get_group_schedules(group_id)
        if group_schedules is None:
            return None
        return next(
            (
                item
                for item in group_schedules.get("schedules", [])
                if item.get("meta", {}).get("schedule_id") == schedule_id
            ),
            None,
        )

    async def async_set_remote(
        self,
        group_id: int,
        *,
        work_mode: str | None = None,
        special_mode: str | None = None,
        bypass_rotation: str | None = None,
        remote_control_work_mode: str | None = None,
        remote_control_speed: int | None = None,
    ) -> None:
        """Send a remote control command, echoing unchanged fields (read-modify-write)."""
        group = self.get_group(group_id)
        if group is None:
            raise IVentError(f"Unknown group {group_id}")
        remote = group.remote
        write = {
            "work_mode": work_mode if work_mode is not None else remote.work_mode,
            "special_mode": special_mode if special_mode is not None else remote.special_mode,
            "bypass_rotation": bypass_rotation if bypass_rotation is not None else remote.bypass_rotation,
            "remote_control_work_mode": (
                remote_control_work_mode
                if remote_control_work_mode is not None
                else remote.remote_control_work_mode
            ),
            "remote_control_speed": (
                remote_control_speed if remote_control_speed is not None else remote.remote_control_speed
            ),
        }
        await self.api.async_modify_group(group_id, remote_work_mode=write)
        await self.async_request_refresh()

    async def async_set_led_mode(self, group_id: int, led_mode: str) -> None:
        """Set the LED work mode of a group."""
        await self.api.async_modify_group(group_id, led_mode=led_mode)
        await self.async_request_refresh()

    async def async_set_buzzer_mode(self, group_id: int, buzzer_mode: str) -> None:
        """Set the buzzer work mode of a group."""
        await self.api.async_modify_group(group_id, buzzer_mode=buzzer_mode)
        await self.async_request_refresh()

    async def async_rename_group(self, group_id: int, name: str) -> None:
        """Rename a group."""
        await self.api.async_modify_group(group_id, name=name)
        await self.async_request_refresh()

    async def async_set_device_reverse_flow(self, mac: str, reverse_flow: bool) -> None:
        """Invert the fan direction of a device."""
        await self.api.async_modify_device(mac, reverse_flow=reverse_flow)
        await self.async_request_refresh()

    async def _async_write_schedules(
        self,
        group_id: int,
        items: list[dict[str, Any]],
        *,
        enable_schedule: bool | None = None,
        bump_last_modified: bool = True,
    ) -> None:
        group = self.get_group(group_id)
        if group is None:
            raise IVentError(f"Unknown group {group_id}")
        group_schedules = self.get_group_schedules(group_id) or {}
        if bump_last_modified:
            now = int(time.time())
            for item in items:
                item.setdefault("meta", {})["last_modified"] = now
        payload = {
            "id": group_id,
            "name": group_schedules.get("name", group.name),
            "enable_schedule": (
                enable_schedule
                if enable_schedule is not None
                else group_schedules.get("enable_schedule", group.enable_schedule)
            ),
            "schedules": items,
        }
        await self.api.async_modify_schedules([payload])
        await self.async_request_refresh()

    async def async_set_schedules_enabled(self, group_id: int, enabled: bool) -> None:
        """Enable or disable the schedules feature of a group."""
        group_schedules = self.get_group_schedules(group_id)
        items = deepcopy(group_schedules["schedules"]) if group_schedules else []
        await self._async_write_schedules(group_id, items, enable_schedule=enabled, bump_last_modified=False)

    async def async_update_schedule_item(
        self,
        group_id: int,
        schedule_id: int,
        *,
        hour: int | None = None,
        minute: int | None = None,
        days: int | None = None,
        enabled: bool | None = None,
        work_mode: str | None = None,
        special_mode: str | None = None,
    ) -> None:
        """Update fields of one schedule item and write the group schedules back."""
        group_schedules = self.get_group_schedules(group_id)
        if group_schedules is None:
            raise IVentError(f"No schedules found for group {group_id}")
        items = deepcopy(group_schedules["schedules"])
        for item in items:
            if item.get("meta", {}).get("schedule_id") != schedule_id:
                continue
            if hour is not None:
                item["repeat"]["hour"] = hour
            if minute is not None:
                item["repeat"]["minute"] = minute
            if days is not None:
                item["repeat"]["days"] = days
            if enabled is not None:
                item["header"]["schedule_item_enabled"] = enabled
            if work_mode is not None:
                item["action"]["work_mode"] = work_mode
            if special_mode is not None:
                item["action"]["special_mode"] = special_mode
        await self._async_write_schedules(group_id, items)

    async def async_add_schedule(
        self,
        group_id: int,
        *,
        hour: int,
        minute: int,
        days: int,
        work_mode: str,
        special_mode: str,
        enabled: bool = True,
    ) -> None:
        """Add a new schedule item to a group."""
        group_schedules = self.get_group_schedules(group_id)
        items = deepcopy(group_schedules["schedules"]) if group_schedules else []
        existing_ids = {item["meta"]["schedule_id"] for item in items}
        schedule_id = random.getrandbits(24)
        while schedule_id in existing_ids:
            schedule_id = random.getrandbits(24)
        items.append(
            {
                "header": {"schedule_item_enabled": enabled},
                "repeat": {"days": days, "hour": hour, "minute": minute},
                "action": {"work_mode": work_mode, "special_mode": special_mode},
                "meta": {"schedule_type": 0, "schedule_id": schedule_id, "last_modified": int(time.time())},
            }
        )
        await self._async_write_schedules(group_id, items)

    async def async_remove_schedule(self, group_id: int, schedule_id: int) -> None:
        """Remove a schedule item from a group."""
        group_schedules = self.get_group_schedules(group_id)
        if group_schedules is None:
            raise IVentError(f"No schedules found for group {group_id}")
        items = [
            item
            for item in deepcopy(group_schedules["schedules"])
            if item.get("meta", {}).get("schedule_id") != schedule_id
        ]
        await self._async_write_schedules(group_id, items)
