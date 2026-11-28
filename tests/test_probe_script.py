"""Tests for the standalone API probe script (scripts/ivent_api_probe.py)."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "ivent_api_probe.py"
spec = importlib.util.spec_from_file_location("ivent_api_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(probe)

INFO = {
    "network_hash": 123,
    "groups": [
        {
            "id": 7,
            "name": "Attic",
            "remote": {
                "work_mode": "IVentOn",
                "special_mode": "IVentSpecialOff",
                "bypass_rotation": "BypassForward",
                "remote_control_work_mode": "Normal",
                "remote_control_speed": 2,
                "special_mode_ends_at": 0,
            },
            "enable_schedule": True,
            "led_work_mode": "LedOnMode",
            "buzzer_work_mode": "BuzzerOffMode",
            "devices": [
                {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "rssi": -60,
                    "alive": True,
                    "reverse_flow": False,
                    "device_name": "Vent 1",
                    "firmware_version": 3,
                    "status_esp": 0,
                }
            ],
        }
    ],
}


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, handler) -> list:
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req)
        return handler(req)

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_info_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A 200 on /info prints the group summary and exits 0."""
    calls = _patch_urlopen(monkeypatch, lambda req: FakeResponse(200, INFO))
    rc = probe.main(["--key", "k", "--loc", "42", "info"])
    assert rc == 0
    assert calls[0].headers["Authorization"] == "Bearer k"
    assert "/live/42/info" in calls[0].full_url
    out = capsys.readouterr().out
    assert "HTTP 200" in out
    assert "Group 7: 'Attic'" in out
    assert "work_mode=IVentOn speed=2" in out


def test_bearer_prefix_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pasted 'Bearer <key>' value is normalized before sending."""
    calls = _patch_urlopen(monkeypatch, lambda req: FakeResponse(200, INFO))
    assert probe.main(["--key", " Bearer secret\n", "--loc", "42", "info"]) == 0
    assert calls[0].headers["Authorization"] == "Bearer secret"


def test_401_hint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A 401 prints the regenerate-the-key hint and exits 1."""

    def handler(req):
        raise probe.urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"invalid api key"}')
        )

    _patch_urlopen(monkeypatch, handler)
    rc = probe.main(["--key", "stale", "--loc", "42", "info"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "HTTP 401" in out
    assert "Regenerate it" in out


def test_echo_sends_current_values_unchanged(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The echo write test POSTs modify_group with the current remote values."""
    posts = []

    def handler(req):
        if req.method == "GET":
            return FakeResponse(200, INFO)
        posts.append(json.loads(req.data.decode()))
        return FakeResponse(200, None)

    _patch_urlopen(monkeypatch, handler)
    rc = probe.main(["--key", "k", "--loc", "42", "echo"])
    assert rc == 0
    assert posts == [
        {
            "group_id": 7,
            "remote_work_mode": {
                "work_mode": "IVentOn",
                "special_mode": "IVentSpecialOff",
                "bypass_rotation": "BypassForward",
                "remote_control_work_mode": "Normal",
                "remote_control_speed": 2,
            },
        }
    ]
    assert "write path OK" in capsys.readouterr().out
