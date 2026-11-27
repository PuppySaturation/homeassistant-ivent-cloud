"""Async client for the i-Vent Smart Home Cloud API."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import BASE_URL, REQUEST_TIMEOUT_SECONDS


class IVentError(Exception):
    """Base exception for i-Vent API errors."""


class IVentAuthError(IVentError):
    """Authentication failed (401/403)."""


class IVentNotFoundError(IVentError):
    """Location or resource not found (404)."""


class IVentConnectionError(IVentError):
    """Network or timeout error while talking to the cloud."""


class IVentApiError(IVentError):
    """Unexpected API response."""

    def __init__(self, status: int, body: str) -> None:
        """Initialize with HTTP status and response body."""
        super().__init__(f"i-Vent API error {status}: {body}")
        self.status = status


@dataclass
class LiveDevice:
    """A physical ventilation device (LiveDevice in the API)."""

    mac_address: str
    rssi: int
    alive: bool
    reverse_flow: bool
    device_name: str
    firmware_version: int
    status_esp: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiveDevice:
        """Create from an API response dict."""
        return cls(
            mac_address=data["mac_address"],
            rssi=data["rssi"],
            alive=data["alive"],
            reverse_flow=data["reverse_flow"],
            device_name=data["device_name"],
            firmware_version=data["firmware_version"],
            status_esp=data["status_esp"],
        )


@dataclass
class RemoteControl:
    """RemoteControlMessageType: the controllable state of a group."""

    work_mode: str
    special_mode: str
    bypass_rotation: str
    remote_control_work_mode: str
    remote_control_speed: int
    special_mode_ends_at: int
    current_mode_duration_in: int | None = None
    current_mode_duration_out: int | None = None
    work_mode_changed_at: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemoteControl:
        """Create from an API response dict."""
        return cls(
            work_mode=data["work_mode"],
            special_mode=data["special_mode"],
            bypass_rotation=data["bypass_rotation"],
            remote_control_work_mode=data["remote_control_work_mode"],
            remote_control_speed=data["remote_control_speed"],
            special_mode_ends_at=data["special_mode_ends_at"],
            current_mode_duration_in=data.get("current_mode_duration_in"),
            current_mode_duration_out=data.get("current_mode_duration_out"),
            work_mode_changed_at=data.get("work_mode_changed_at"),
        )

    def to_write_dict(self) -> dict[str, Any]:
        """Return a RemoteControlMessageTypeWrite payload (device-set fields excluded)."""
        return {
            "work_mode": self.work_mode,
            "special_mode": self.special_mode,
            "bypass_rotation": self.bypass_rotation,
            "remote_control_work_mode": self.remote_control_work_mode,
            "remote_control_speed": self.remote_control_speed,
        }


@dataclass
class LiveGroup:
    """A ventilation group (LiveGroup in the API)."""

    id: int
    name: str
    remote: RemoteControl
    enable_schedule: bool
    led_work_mode: str
    buzzer_work_mode: str
    devices: list[LiveDevice] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiveGroup:
        """Create from an API response dict."""
        return cls(
            id=data["id"],
            name=data["name"],
            remote=RemoteControl.from_dict(data["remote"]),
            enable_schedule=data["enable_schedule"],
            led_work_mode=data["led_work_mode"],
            buzzer_work_mode=data["buzzer_work_mode"],
            devices=[LiveDevice.from_dict(d) for d in data.get("devices", [])],
        )


@dataclass
class LiveInfo:
    """LiveInfo: overall system state, meant to be polled."""

    network_hash: int
    groups: list[LiveGroup]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiveInfo:
        """Create from an API response dict."""
        return cls(
            network_hash=data["network_hash"],
            groups=[LiveGroup.from_dict(g) for g in data.get("groups", [])],
        )


class IVentApiClient:
    """Thin async wrapper around the i-Vent cloud API for one location."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str, loc_id: int) -> None:
        """Initialize the client with a session, bearer API key and location id."""
        self._session = session
        self._base_url = f"{BASE_URL}/live/{loc_id}"
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}/{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with self._session.request(method, url, headers=self._headers, json=payload) as response:
                    if response.status in (401, 403):
                        raise IVentAuthError("Invalid API key")
                    if response.status == 404:
                        raise IVentNotFoundError(f"Not found: {url}")
                    if response.status >= 400:
                        raise IVentApiError(response.status, await response.text())
                    text = await response.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise IVentConnectionError(f"Error communicating with i-Vent cloud: {err}") from err
        return json.loads(text) if text else None

    async def async_get_info(self) -> LiveInfo:
        """Get the overall system state (GET /live/{loc_id}/info)."""
        return LiveInfo.from_dict(await self._request("GET", "info"))

    async def async_get_schedules(self) -> list[dict[str, Any]]:
        """Get the schedules for the location (GET /live/{loc_id}/schedules)."""
        data = await self._request("GET", "schedules")
        return data or []

    async def async_create_group(self, name: str) -> int:
        """Create a group with a random id (POST /live/{loc_id}/create_group)."""
        data = await self._request("POST", "create_group", {"name": name})
        return int(data["group_id"])

    async def async_modify_group(
        self,
        group_id: int,
        *,
        name: str | None = None,
        delete: bool | None = None,
        led_mode: str | None = None,
        buzzer_mode: str | None = None,
        remote_work_mode: dict[str, Any] | None = None,
    ) -> None:
        """Modify group settings or send remote control commands."""
        payload: dict[str, Any] = {"group_id": group_id}
        if name is not None:
            payload["name"] = name
        if delete is not None:
            payload["delete"] = delete
        if led_mode is not None:
            payload["led_mode"] = led_mode
        if buzzer_mode is not None:
            payload["buzzer_mode"] = buzzer_mode
        if remote_work_mode is not None:
            payload["remote_work_mode"] = remote_work_mode
        await self._request("POST", "modify_group", payload)

    async def async_modify_device(
        self,
        device_mac: str,
        *,
        name: str | None = None,
        group_id: int | None = None,
        reverse_flow: bool | None = None,
    ) -> None:
        """Modify a device: rename, move to another group, invert fan direction."""
        payload: dict[str, Any] = {"device_mac": device_mac}
        if name is not None:
            payload["name"] = name
        if group_id is not None:
            payload["group_id"] = group_id
        if reverse_flow is not None:
            payload["reverse_flow"] = reverse_flow
        await self._request("POST", "modify_device", payload)

    async def async_modify_schedules(self, schedules: list[dict[str, Any]]) -> None:
        """Modify scheduled actions (POST /live/{loc_id}/modify_schedules)."""
        await self._request("POST", "modify_schedules", {"schedules": schedules})
