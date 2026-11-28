"""Tests for the standalone API probe script (scripts/ivent_api_probe.py).

The probe uses the integration's own client (custom_components/ivent/api.py),
so these tests intercept its aiohttp session with the aioclient_mock.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant

from .conftest import API_KEY, INFO_RESPONSE, SCHEDULES_RESPONSE

SCRIPT = Path(__file__).parent.parent / "scripts" / "ivent_api_probe.py"
spec = importlib.util.spec_from_file_location("ivent_api_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(probe)

INFO_URL = f"{probe.DEFAULT_BASE_URL}/live/42/info"
SCHEDULES_URL = f"{probe.DEFAULT_BASE_URL}/live/42/schedules"
MODIFY_GROUP_URL = f"{probe.DEFAULT_BASE_URL}/live/42/modify_group"

REMOTE_WRITE = {
    "work_mode": "IVentOn",
    "special_mode": "IVentSpecialOff",
    "bypass_rotation": "BypassForward",
    "remote_control_work_mode": "Normal",
    "remote_control_speed": 2,
}


@pytest.fixture
def probe_session(hass: HomeAssistant, aioclient_mock, monkeypatch: pytest.MonkeyPatch):
    """Route the probe script's aiohttp.ClientSession through the aioclient_mock."""
    monkeypatch.setattr(
        probe.aiohttp, "ClientSession", lambda *a, **k: aioclient_mock.create_session(hass.loop)
    )
    return aioclient_mock


async def test_info_success(hass, probe_session, capsys: pytest.CaptureFixture) -> None:
    """A 200 on /info prints the group summary and exits 0."""
    probe_session.get(INFO_URL, json=INFO_RESPONSE)
    rc = await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", "42", "info"]))
    assert rc == 0
    method, url, _data, headers = probe_session.mock_calls[0]
    assert method == "GET"
    assert str(url) == INFO_URL
    assert headers["Authorization"] == f"Bearer {API_KEY}"
    out = capsys.readouterr().out
    assert "200 OK" in out
    assert "Group 1: 'Living room'" in out
    assert "work_mode=IVentOn speed=2" in out


async def test_bearer_prefix_stripped(hass, probe_session) -> None:
    """A pasted 'Bearer <key>' value is normalized before sending."""
    probe_session.get(INFO_URL, json=INFO_RESPONSE)
    rc = await probe.run_probe(probe.parse_args(["--key", "  Bearer secret\n", "--loc", "42", "info"]))
    assert rc == 0
    _method, _url, _data, headers = probe_session.mock_calls[0]
    assert headers["Authorization"] == "Bearer secret"


async def test_401_hint(hass, probe_session, capsys: pytest.CaptureFixture) -> None:
    """A 401 prints the regenerate-the-key hint and exits 1."""
    probe_session.get(INFO_URL, status=401, text='{"error":"invalid api key"}')
    rc = await probe.run_probe(probe.parse_args(["--key", "stale", "--loc", "42", "info"]))
    assert rc == 1
    out = capsys.readouterr().out
    assert "HTTP 401" in out
    assert "regenerate the API key" in out


async def test_404_hint(hass, probe_session, capsys: pytest.CaptureFixture) -> None:
    """A 404 prints the loc_id hint and exits 1."""
    probe_session.get(INFO_URL, status=404)
    rc = await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", "42", "info"]))
    assert rc == 1
    assert "loc_id" in capsys.readouterr().out


async def test_schedules(hass, probe_session, capsys: pytest.CaptureFixture) -> None:
    """The schedules command prints the schedule items."""
    probe_session.get(SCHEDULES_URL, json=SCHEDULES_RESPONSE)
    rc = await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", "42", "schedules"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "schedule_id=123456" in out
    assert "days=Mon, Tue, Wed, Thu, Fri" in out


async def test_echo_sends_current_values_unchanged(
    hass, probe_session, capsys: pytest.CaptureFixture
) -> None:
    """The echo write test POSTs modify_group with the current remote values unchanged."""
    probe_session.get(INFO_URL, json=INFO_RESPONSE)
    probe_session.post(MODIFY_GROUP_URL, status=200)
    rc = await probe.run_probe(probe.parse_args(["--key", API_KEY, "--loc", "42", "echo"]))
    assert rc == 0
    posts = [c for c in probe_session.mock_calls if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2] == {"group_id": 1, "remote_work_mode": REMOTE_WRITE}
    assert "write path OK" in capsys.readouterr().out
