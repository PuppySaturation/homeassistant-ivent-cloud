"""Tests for setting up the i-Vent Cloud integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.ivent.const import DOMAIN

from .conftest import INFO_URL, mock_cloud


async def test_setup_entry(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test the entry sets up and creates the expected entities."""
    mock_cloud(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    fan = hass.states.get("fan.living_room")
    assert fan is not None
    assert fan.state == "on"
    assert fan.attributes["percentage"] == 67
    assert fan.attributes["preset_mode"] == "On"
    assert "Bypass 2" in fan.attributes["preset_modes"]

    assert hass.states.get("select.living_room_special_mode").state == "Off"
    assert hass.states.get("select.living_room_bypass_rotation").state == "Forward"
    assert hass.states.get("select.living_room_remote_control_mode").state == "Normal"
    assert hass.states.get("select.living_room_led_mode").state == "On"
    assert hass.states.get("select.living_room_buzzer_mode").state == "Off"

    assert hass.states.get("switch.living_room_schedules_enabled").state == "on"
    assert hass.states.get("switch.living_room_schedule_item_enabled").state == "on"
    assert hass.states.get("switch.vent_1_reverse_flow").state == "off"

    assert hass.states.get("binary_sensor.vent_1_online").state == "on"
    assert hass.states.get("sensor.vent_1_signal_strength").state == "-55"

    assert hass.states.get("time.living_room_schedule_time").state == "22:00:00"
    assert hass.states.get("select.living_room_schedule_days").state == "Weekdays"
    assert hass.states.get("select.living_room_schedule_work_mode").state == "On"
    assert hass.states.get("select.living_room_schedule_special_mode").state == "Night 1"


async def test_setup_retry_on_api_error(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test a server error during setup results in SETUP_RETRY."""
    aioclient_mock.get(INFO_URL, status=500, text="server error")
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test a 401 during setup results in SETUP_ERROR and a reauth flow."""
    aioclient_mock.get(INFO_URL, status=401)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test unloading the entry removes it from hass.data."""
    mock_cloud(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data or not hass.data[DOMAIN]
