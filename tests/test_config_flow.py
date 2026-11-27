"""Tests for the i-Vent Cloud config flow."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ivent.const import BASE_URL, CONF_BASE_URL, CONF_LOC_ID, DOMAIN

from .conftest import API_KEY, INFO_RESPONSE, INFO_URL, LOC_ID, SCHEDULES_RESPONSE, mock_cloud


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    """Test a successful user flow creates an entry."""
    mock_cloud(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "i-Vent location 12345 (1 group)"
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID, CONF_BASE_URL: BASE_URL}


async def test_user_flow_custom_base_url(hass: HomeAssistant, aioclient_mock) -> None:
    """Test that a custom base URL is used for validation and stored."""
    mock_base = "https://ivent-mock.local/api/v1"
    aioclient_mock.get(f"{mock_base}/live/{LOC_ID}/info", json=INFO_RESPONSE)
    aioclient_mock.get(f"{mock_base}/live/{LOC_ID}/schedules", json=SCHEDULES_RESPONSE)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID, CONF_BASE_URL: mock_base + "/"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BASE_URL] == mock_base
    assert str(aioclient_mock.mock_calls[0][1]).startswith(mock_base)


async def test_user_flow_normalizes_api_key(hass: HomeAssistant, aioclient_mock) -> None:
    """Test that whitespace and an accidental 'Bearer ' prefix are stripped from the key."""
    mock_cloud(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "  Bearer test-api-key\n", CONF_LOC_ID: LOC_ID}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == API_KEY
    _method, _url, _data, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == f"Bearer {API_KEY}"


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    """Test a 401 from the API shows invalid_auth."""
    aioclient_mock.get(INFO_URL, status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key", CONF_LOC_ID: LOC_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_invalid_location(hass: HomeAssistant, aioclient_mock) -> None:
    """Test a 404 from the API shows invalid_location."""
    aioclient_mock.get(f"{BASE_URL}/live/999/info", status=404)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_LOC_ID: 999}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_location"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    """Test a connection error shows cannot_connect."""
    aioclient_mock.get(INFO_URL, exc=aiohttp.ClientConnectionError("boom"))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_location(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test the same location cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_LOC_ID: LOC_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test the reauth flow updates the API key."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "new-key"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-key"


async def test_options_flow(hass: HomeAssistant, aioclient_mock, mock_config_entry) -> None:
    """Test the options flow sets the scan interval."""
    mock_cloud(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 60})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"scan_interval": 60}
