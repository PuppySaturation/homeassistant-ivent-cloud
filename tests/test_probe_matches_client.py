"""Cross-check: the standalone probe script and the HA API client must send identical requests.

The probe script (scripts/ivent_api_probe.py) is used outside HA for diagnosis;
HA itself uses custom_components/ivent/api.py. These tests run both against the
same canned responses and assert the requests match, so probe output is
meaningful evidence about what the integration will send.
"""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.ivent.api import IVentApiClient
from custom_components.ivent.const import BASE_URL

from .conftest import API_KEY
from .test_probe_script import INFO, FakeResponse, probe


async def test_probe_and_ha_client_send_identical_get(
    hass: HomeAssistant, aioclient_mock, monkeypatch, capsys
) -> None:
    """GET /info: probe (urllib) and IVentApiClient (aiohttp) must produce the same request."""
    loc = "42"
    aioclient_mock.get(f"{BASE_URL}/live/{loc}/info", json=INFO)
    client = IVentApiClient(async_get_clientsession(hass), API_KEY, loc)

    captured = []

    def fake_urlopen(req, timeout=0):
        captured.append(req)
        return FakeResponse(200, INFO)

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    assert probe.main(["--key", API_KEY, "--loc", loc, "info"]) == 0
    capsys.readouterr()

    info = await client.async_get_info()
    assert info.network_hash == INFO["network_hash"]

    method, url, _data, headers = aioclient_mock.mock_calls[0]
    req = captured[0]
    assert method == req.method == "GET"
    assert str(url) == req.full_url
    assert headers["Authorization"] == req.headers["Authorization"] == f"Bearer {API_KEY}"


async def test_probe_echo_and_ha_client_modify_group_match(
    hass: HomeAssistant, aioclient_mock, monkeypatch, capsys
) -> None:
    """The probe's `echo` POST and IVentApiClient.async_modify_group must send the same payload."""
    loc = "42"
    group = INFO["groups"][0]
    aioclient_mock.post(f"{BASE_URL}/live/{loc}/modify_group", status=200)

    posts = []

    def fake_urlopen(req, timeout=0):
        if req.method == "GET":
            return FakeResponse(200, INFO)
        posts.append((req.full_url, req.method, json.loads(req.data.decode()), req.headers["Authorization"]))
        return FakeResponse(200, None)

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    assert probe.main(["--key", API_KEY, "--loc", loc, "echo"]) == 0
    capsys.readouterr()

    client = IVentApiClient(async_get_clientsession(hass), API_KEY, loc)
    await client.async_modify_group(
        group["id"], remote_work_mode=probe.remote_write_payload(group["remote"])
    )

    method, url, data, headers = aioclient_mock.mock_calls[-1]
    p_url, p_method, p_data, p_auth = posts[0]
    assert method == p_method == "POST"
    assert str(url) == p_url
    assert data == p_data
    assert headers["Authorization"] == p_auth == f"Bearer {API_KEY}"
