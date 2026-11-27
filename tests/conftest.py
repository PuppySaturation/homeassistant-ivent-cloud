"""Fixtures and mock API data for i-Vent Cloud tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ivent.const import BASE_URL, CONF_LOC_ID, DOMAIN

LOC_ID = 12345
API_KEY = "test-api-key"
GROUP_ID = 1
DEVICE_MAC = "AA:BB:CC:DD:EE:FF"
SCHEDULE_ID = 123456

INFO_URL = f"{BASE_URL}/live/{LOC_ID}/info"
SCHEDULES_URL = f"{BASE_URL}/live/{LOC_ID}/schedules"

INFO_RESPONSE: dict[str, Any] = {
    "network_hash": 987654321,
    "groups": [
        {
            "id": GROUP_ID,
            "name": "Living room",
            "remote": {
                "work_mode": "IVentOn",
                "special_mode": "IVentSpecialOff",
                "bypass_rotation": "BypassForward",
                "remote_control_work_mode": "Normal",
                "remote_control_speed": 2,
                "special_mode_ends_at": 0,
                "current_mode_duration_in": 10,
                "current_mode_duration_out": 5,
                "work_mode_changed_at": 1700000000,
            },
            "enable_schedule": True,
            "led_work_mode": "LedOnMode",
            "buzzer_work_mode": "BuzzerOffMode",
            "devices": [
                {
                    "mac_address": DEVICE_MAC,
                    "rssi": -55,
                    "alive": True,
                    "reverse_flow": False,
                    "device_name": "Vent 1",
                    "firmware_version": 12,
                    "status_esp": 0,
                }
            ],
        }
    ],
}

SCHEDULE_ITEM: dict[str, Any] = {
    "header": {"schedule_item_enabled": True},
    "repeat": {"days": 31, "hour": 22, "minute": 0},
    "action": {"work_mode": "IVentOn", "special_mode": "IVentNight1"},
    "meta": {"schedule_type": 0, "schedule_id": SCHEDULE_ID, "last_modified": 1700000000},
}

SCHEDULES_RESPONSE: list[dict[str, Any]] = [
    {
        "id": GROUP_ID,
        "name": "Living room",
        "enable_schedule": True,
        "schedules": [SCHEDULE_ITEM],
    }
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Generator[None]:
    """Enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test location."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"i-Vent location {LOC_ID}",
        unique_id=str(LOC_ID),
        data={CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID},
    )


def mock_cloud(aioclient_mock: Any) -> None:
    """Register mock responses for all i-Vent endpoints."""
    aioclient_mock.get(INFO_URL, json=INFO_RESPONSE)
    aioclient_mock.get(SCHEDULES_URL, json=SCHEDULES_RESPONSE)
    for path in ("create_group", "modify_group", "modify_device", "modify_schedules"):
        aioclient_mock.post(f"{BASE_URL}/live/{LOC_ID}/{path}", status=200)


def last_post_payload(aioclient_mock: Any, path: str) -> dict[str, Any]:
    """Return the JSON payload of the last POST to the given path."""
    for method, url, data, _headers in reversed(aioclient_mock.mock_calls):
        if method.lower() == "post" and str(url).endswith(f"/{path}"):
            return data
    raise AssertionError(f"No POST to {path} was made")
