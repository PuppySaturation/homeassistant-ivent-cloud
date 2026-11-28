"""Cross-check: the probe script must use the same client code as HA.

The probe (scripts/ivent_api_probe.py) loads custom_components/ivent/api.py and
sends requests through IVentApiClient - the exact class HA uses. These tests run
the probe and the client directly against the same mocked HTTP layer and assert
the recorded requests are identical.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.ivent.api import IVentApiClient
from custom_components.ivent.const import BASE_URL

from .conftest import API_KEY, INFO_RESPONSE
from .test_probe_script import REMOTE_WRITE, probe


async def test_probe_and_ha_client_send_identical_get(
    hass: HomeAssistant, aioclient_mock, monkeypatch, capsys
) -> None:
    """Probe `info` and IVentApiClient.async_get_info must produce the same request."""
    loc = "42"
    url = f"{BASE_URL}/live/{loc}/info"
    aioclient_mock.get(url, json=INFO_RESPONSE)
    monkeypatch.setattr(
        probe.aiohttp, "ClientSession", lambda *a, **k: aioclient_mock.create_session(hass.loop)
    )

    assert await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", loc, "info"])) == 0
    capsys.readouterr()

    client = IVentApiClient(async_get_clientsession(hass), API_KEY, loc)
    await client.async_get_info()

    probe_call, client_call = aioclient_mock.mock_calls
    assert probe_call == client_call
    assert probe_call[0] == "GET"
    assert str(probe_call[1]) == url
    assert probe_call[3]["Authorization"] == f"Bearer {API_KEY}"


async def test_probe_echo_and_ha_client_modify_group_match(
    hass: HomeAssistant, aioclient_mock, monkeypatch, capsys
) -> None:
    """Probe `echo` and IVentApiClient.async_modify_group must send the same POST payload."""
    loc = "42"
    aioclient_mock.get(f"{BASE_URL}/live/{loc}/info", json=INFO_RESPONSE)
    aioclient_mock.post(f"{BASE_URL}/live/{loc}/modify_group", status=200)
    monkeypatch.setattr(
        probe.aiohttp, "ClientSession", lambda *a, **k: aioclient_mock.create_session(hass.loop)
    )

    assert await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", loc, "echo"])) == 0
    capsys.readouterr()

    client = IVentApiClient(async_get_clientsession(hass), API_KEY, loc)
    await client.async_modify_group(1, remote_work_mode=dict(REMOTE_WRITE))

    probe_post = next(c for c in aioclient_mock.mock_calls if c[0] == "POST")
    client_post = aioclient_mock.mock_calls[-1]
    assert probe_post == client_post
    assert probe_post[2] == {"group_id": 1, "remote_work_mode": REMOTE_WRITE}
