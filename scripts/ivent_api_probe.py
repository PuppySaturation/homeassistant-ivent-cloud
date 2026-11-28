#!/usr/bin/env python3
"""Probe the i-Vent Smart Home Cloud API outside Home Assistant.

Read-only by default (`info`, `schedules`). The `echo` command performs a
read-modify-write POST that sends the current values back unchanged, to
verify the write path without changing anything.

Credentials come from --key/--loc arguments or the IVENT_API_KEY /
IVENT_LOC_ID environment variables. Nothing is stored or logged.

Requires Python 3.11+ (standard library only, no pip install needed).

Examples:
    IVENT_API_KEY=... IVENT_LOC_ID=... python3 scripts/ivent_api_probe.py info
    python3 scripts/ivent_api_probe.py --key ... --loc ... schedules --full
    python3 scripts/ivent_api_probe.py echo        # write-path test, no state change
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

DEFAULT_BASE_URL = "https://cloud.i-vent.com/api/v1"
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # bit 0 = Monday


def api_request(
    base_url: str,
    loc_id: str,
    api_key: str,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 30,
) -> tuple[int | None, object, str]:
    """Perform one API request; return (status, parsed_body, url)."""
    url = f"{base_url.rstrip('/')}/live/{loc_id}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body else None), url
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        try:
            parsed: object = json.loads(raw)
        except ValueError:
            parsed = raw
        return err.code, parsed, url
    except urllib.error.URLError as err:
        return None, f"connection error: {err.reason}", url


def explain_error(status: int | None, body: object) -> str:
    """Return a human-readable hint for a failed request."""
    if status in (401, 403):
        return (
            "authentication rejected - the API key is wrong, revoked or expired. "
            "Regenerate it in the i-Vent web UI and use the newest value "
            "(regenerating invalidates the old key). Also make sure your shell variable "
            "holds the new key, not a stale one."
        )
    if status == 404:
        return (
            "location not found - check the loc_id (the number in "
            "/api/v1/live/<loc_id>/info as used by the i-Vent app itself)."
        )
    if status is None:
        return "could not reach the API - check network, DNS, proxy or VPN."
    return f"HTTP {status}: {body}"


def days_to_names(bitmask: int) -> str:
    """Convert the schedule days bitmask (bit 0 = Monday) to day names."""
    return ", ".join(DAY_NAMES[i] for i in range(7) if bitmask & (1 << i)) or "-"


def print_info(data: dict, full: bool) -> None:
    """Print a summary of GET /info (or the raw JSON with --full)."""
    if full:
        print(json.dumps(data, indent=2))
        return
    print(f"network_hash: {data.get('network_hash')}")
    for group in data.get("groups", []):
        remote = group.get("remote", {})
        print(f"\nGroup {group.get('id')}: {group.get('name')!r}")
        print(
            f"  work_mode={remote.get('work_mode')} speed={remote.get('remote_control_speed')} "
            f"special_mode={remote.get('special_mode')} special_mode_ends_at={remote.get('special_mode_ends_at')}"
        )
        print(
            f"  bypass_rotation={remote.get('bypass_rotation')} rc_mode={remote.get('remote_control_work_mode')} "
            f"schedules_enabled={group.get('enable_schedule')} "
            f"led={group.get('led_work_mode')} buzzer={group.get('buzzer_work_mode')}"
        )
        for dev in group.get("devices", []):
            print(
                f"  device {dev.get('mac_address')} {dev.get('device_name')!r} alive={dev.get('alive')} "
                f"rssi={dev.get('rssi')}dBm reverse_flow={dev.get('reverse_flow')} "
                f"fw={dev.get('firmware_version')} esp={dev.get('status_esp')}"
            )


def print_schedules(data: list, full: bool) -> None:
    """Print a summary of GET /schedules (or the raw JSON with --full)."""
    if full:
        print(json.dumps(data, indent=2))
        return
    for group in data:
        print(f"\nGroup {group.get('id')}: {group.get('name')!r} enable_schedule={group.get('enable_schedule')}")
        for item in group.get("schedules", []):
            repeat = item.get("repeat", {})
            action = item.get("action", {})
            meta = item.get("meta", {})
            header = item.get("header", {})
            when = f"{repeat.get('hour'):02d}:{repeat.get('minute'):02d}"
            last_modified = meta.get("last_modified")
            lm_str = (
                datetime.fromtimestamp(last_modified, tz=UTC).isoformat() if last_modified else "?"
            )
            print(
                f"  schedule_id={meta.get('schedule_id')} enabled={header.get('schedule_item_enabled')} "
                f"at={when} days={days_to_names(repeat.get('days', 0))} -> work_mode={action.get('work_mode')} "
                f"special_mode={action.get('special_mode')} (last_modified={lm_str})"
            )


def remote_write_payload(remote: dict) -> dict:
    """Build a RemoteControlMessageTypeWrite payload from current state (device-set fields excluded)."""
    return {
        "work_mode": remote["work_mode"],
        "special_mode": remote["special_mode"],
        "bypass_rotation": remote["bypass_rotation"],
        "remote_control_work_mode": remote["remote_control_work_mode"],
        "remote_control_speed": remote["remote_control_speed"],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the probe; return a process exit code."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["info", "schedules", "echo"], nargs="?", default="info")
    parser.add_argument("--key", default=os.environ.get("IVENT_API_KEY"), help="API key (or env IVENT_API_KEY)")
    parser.add_argument("--loc", default=os.environ.get("IVENT_LOC_ID"), help="location id (or env IVENT_LOC_ID)")
    parser.add_argument(
        "--base-url", default=os.environ.get("IVENT_BASE_URL", DEFAULT_BASE_URL), help="API base URL override"
    )
    parser.add_argument("--full", action="store_true", help="print raw JSON instead of the summary")
    args = parser.parse_args(argv)

    if not args.key or not args.loc:
        parser.error("API key and location id are required: use --key/--loc or IVENT_API_KEY/IVENT_LOC_ID")
    key = args.key.strip()
    if key.lower().startswith("bearer "):
        key = key[len("bearer ") :].strip()
    loc = str(args.loc).strip()

    if args.command == "echo":
        status, info, url = api_request(args.base_url, loc, key, "GET", "info")
        if status != 200 or not isinstance(info, dict):
            print(f"GET info failed: HTTP {status}\n{explain_error(status, info)}")
            return 1
        groups = info.get("groups") or []
        if not groups:
            print("No groups in this location; nothing to echo.")
            return 0
        group = groups[0]
        payload = {"group_id": group["id"], "remote_work_mode": remote_write_payload(group["remote"])}
        status, body, url = api_request(args.base_url, loc, key, "POST", "modify_group", payload)
        print(f"echo write test on group {group['id']} ({group.get('name')!r}): sent current values unchanged")
    elif args.command == "info":
        status, body, url = api_request(args.base_url, loc, key, "GET", "info")
    else:
        status, body, url = api_request(args.base_url, loc, key, "GET", "schedules")

    print(f"{args.command.upper()} {url} -> HTTP {status}")
    if status is None or not 200 <= status < 300:
        print(explain_error(status, body))
        return 1
    if args.command == "info":
        print_info(body, args.full)  # type: ignore[arg-type]
    elif args.command == "schedules":
        print_schedules(body, args.full)  # type: ignore[arg-type]
    else:
        print("write path OK (values unchanged)" if body is None else json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
