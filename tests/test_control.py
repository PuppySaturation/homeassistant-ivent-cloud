"""Tests for control commands and their API payloads."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.ivent.const import DOMAIN

from .conftest import DEVICE_MAC, GROUP_ID, SCHEDULE_ID, last_post_payload, mock_cloud

FAN = "fan.living_room"
SPECIAL_MODE_SELECT = "select.living_room_special_mode"
LED_SELECT = "select.living_room_led_mode"
SCHEDULES_SWITCH = "switch.living_room_schedules_enabled"
ITEM_SWITCH = "switch.living_room_schedule_item_enabled"
REVERSE_FLOW_SWITCH = "switch.vent_1_reverse_flow"
SCHEDULE_TIME = "time.living_room_schedule_time"
SCHEDULE_DAYS = "select.living_room_schedule_days"

EXPECTED_REMOTE_ECHO = {
    "work_mode": "IVentOn",
    "special_mode": "IVentSpecialOff",
    "bypass_rotation": "BypassForward",
    "remote_control_work_mode": "Normal",
    "remote_control_speed": 2,
}


async def _setup(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    mock_cloud(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_fan_turn_off_sends_full_remote_payload(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Turning the fan off must echo all remote fields (read-modify-write)."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("fan", "turn_off", {"entity_id": FAN}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_group")
    assert payload == {
        "group_id": GROUP_ID,
        "remote_work_mode": {**EXPECTED_REMOTE_ECHO, "work_mode": "IVentWorkOff"},
    }


async def test_fan_set_percentage(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Setting 100% maps to remote_control_speed 3 and keeps the work mode."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 100}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_group")
    assert payload["remote_work_mode"] == {**EXPECTED_REMOTE_ECHO, "remote_control_speed": 3}


async def test_fan_set_preset_mode(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """A preset mode maps to the corresponding IVentWorkMode."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call(
        "fan", "set_preset_mode", {"entity_id": FAN, "preset_mode": "Bypass 2"}, blocking=True
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_group")
    assert payload["remote_work_mode"] == {**EXPECTED_REMOTE_ECHO, "work_mode": "IVentBypass2"}


async def test_special_mode_select(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Selecting Boost only changes special_mode."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": SPECIAL_MODE_SELECT, "option": "Boost"}, blocking=True
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_group")
    assert payload["remote_work_mode"] == {**EXPECTED_REMOTE_ECHO, "special_mode": "IVentBoost"}


async def test_led_mode_select(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """The LED select calls modify_group with led_mode only."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": LED_SELECT, "option": "Off"}, blocking=True
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_group")
    assert payload == {"group_id": GROUP_ID, "led_mode": "LedOffMode"}


async def test_schedules_enabled_switch(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Disabling schedules posts enable_schedule=False with items unchanged."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("switch", "turn_off", {"entity_id": SCHEDULES_SWITCH}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    assert len(payload["schedules"]) == 1
    group_schedules = payload["schedules"][0]
    assert group_schedules["id"] == GROUP_ID
    assert group_schedules["enable_schedule"] is False
    assert group_schedules["schedules"][0]["meta"]["last_modified"] == 1700000000


async def test_reverse_flow_switch(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """The reverse flow switch calls modify_device."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("switch", "turn_on", {"entity_id": REVERSE_FLOW_SWITCH}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_device")
    assert payload == {"device_mac": DEVICE_MAC, "reverse_flow": True}


async def test_schedule_time_set(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Setting the schedule time updates hour/minute and bumps last_modified."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("time", "set_value", {"entity_id": SCHEDULE_TIME, "time": "07:30:00"}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    item = payload["schedules"][0]["schedules"][0]
    assert item["repeat"]["hour"] == 7
    assert item["repeat"]["minute"] == 30
    assert item["meta"]["last_modified"] > 1700000000


async def test_schedule_days_select(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Selecting Weekends maps to the days bitmask 96."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": SCHEDULE_DAYS, "option": "Weekends"}, blocking=True
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    item = payload["schedules"][0]["schedules"][0]
    assert item["repeat"]["days"] == 96


async def test_schedule_item_switch(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Disabling a schedule item sets header.schedule_item_enabled."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    await hass.services.async_call("switch", "turn_off", {"entity_id": ITEM_SWITCH}, blocking=True)
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    item = payload["schedules"][0]["schedules"][0]
    assert item["header"]["schedule_item_enabled"] is False


async def test_add_schedule_service(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """The add_schedule service appends a new item with a fresh schedule_id."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    device = dr.async_get(hass).async_get_device({(DOMAIN, str(GROUP_ID))})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        "add_schedule",
        {
            "device_id": device.id,
            "hour": 7,
            "minute": 30,
            "days": "Weekdays",
            "work_mode": "IVentOn",
            "special_mode": "IVentSpecialOff",
            "enabled": True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    items = payload["schedules"][0]["schedules"]
    assert len(items) == 2
    new_item = items[1]
    assert new_item["repeat"] == {"days": 31, "hour": 7, "minute": 30}
    assert new_item["action"] == {"work_mode": "IVentOn", "special_mode": "IVentSpecialOff"}
    assert new_item["header"] == {"schedule_item_enabled": True}
    assert new_item["meta"]["schedule_id"] != SCHEDULE_ID
    assert 0 <= new_item["meta"]["schedule_id"] < 2**24
    for item in items:
        assert item["meta"]["last_modified"] > 1700000000


async def test_remove_schedule_service(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """The remove_schedule service removes the item by schedule_id."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    device = dr.async_get(hass).async_get_device({(DOMAIN, str(GROUP_ID))})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        "remove_schedule",
        {"device_id": device.id, "schedule_id": SCHEDULE_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    assert payload["schedules"][0]["schedules"] == []


async def test_add_schedule_service_resolves_group_from_physical_device(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Passing a physical device id resolves its parent group."""
    await _setup(hass, aioclient_mock, mock_config_entry)
    device = dr.async_get(hass).async_get_device({(DOMAIN, DEVICE_MAC)})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        "add_schedule",
        {
            "device_id": device.id,
            "hour": 8,
            "minute": 0,
            "days": "Every day",
            "work_mode": "IVentWorkOff",
            "special_mode": "IVentSpecialOff",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    payload = last_post_payload(aioclient_mock, "modify_schedules")
    assert payload["schedules"][0]["id"] == GROUP_ID
    assert len(payload["schedules"][0]["schedules"]) == 2
