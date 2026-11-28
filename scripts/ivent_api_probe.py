#!/usr/bin/env python3
"""Probe the i-Vent Smart Home Cloud API outside Home Assistant.

Uses the exact API client the integration uses in HA
(custom_components/ivent/api.py, IVentApiClient), so probe results match
what Home Assistant sends and receives.

`info` and `schedules` are read-only. `echo` verifies the write path with a
read-modify-write POST that sends the current values back unchanged.

Credentials come from --key/--loc arguments or the IVENT_API_KEY /
IVENT_LOC_ID environment variables. Nothing is stored or logged.

Requirements: Python 3.11+ and aiohttp (`pip install aiohttp`), or any
environment where Home Assistant is installed (it bundles aiohttp).

Examples:
    IVENT_API_KEY=... IVENT_LOC_ID=... python3 scripts/ivent_api_probe.py info
    python3 scripts/ivent_api_probe.py --key ... --loc ... schedules --full
    python3 scripts/ivent_api_probe.py echo        # write-path test, no state change
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # bit 0 = Monday


def load_integration_api() -> types.ModuleType:
    """Import custom_components/ivent/api.py directly by file path.

    Importing the package normally would execute custom_components/ivent/__init__.py,
    which requires Home Assistant. We only need const.py + api.py (which need just
    aiohttp), loaded under a private package name so the relative import resolves.
    """
    pkg = types.ModuleType("ivent_probe_pkg")
    pkg.__path__ = [str(ROOT / "custom_components" / "ivent")]
    sys.modules["ivent_probe_pkg"] = pkg

    def load(name: str, path: Path) -> types.ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    load("ivent_probe_pkg.const", ROOT / "custom_components" / "ivent" / "const.py")
    return load("ivent_probe_pkg.api", ROOT / "custom_components" / "ivent" / "api.py")


api = load_integration_api()
DEFAULT_BASE_URL = api.BASE_URL


def normalize_key(key: str) -> str:
    """Strip whitespace and an accidental 'Bearer ' prefix from the entered key."""
    key = key.strip()
    if key.lower().startswith("bearer "):
        key = key[len("bearer ") :].strip()
    return key


def days_to_names(bitmask: int) -> str:
    """Convert the schedule days bitmask (bit 0 = Monday) to day names."""
    return ", ".join(DAY_NAMES[i] for i in range(7) if bitmask & (1 << i)) or "-"


def print_info(info: api.LiveInfo) -> None:
    """Print a summary of the polled system state."""
    print(f"network_hash: {info.network_hash}")
    for group in info.groups:
        remote = group.remote
        print(f"\nGroup {group.id}: {group.name!r}")
        print(
            f"  work_mode={remote.work_mode} speed={remote.remote_control_speed} "
            f"special_mode={remote.special_mode} special_mode_ends_at={remote.special_mode_ends_at}"
        )
        print(
            f"  bypass_rotation={remote.bypass_rotation} rc_mode={remote.remote_control_work_mode} "
            f"schedules_enabled={group.enable_schedule} led={group.led_work_mode} buzzer={group.buzzer_work_mode}"
        )
        for dev in group.devices:
            print(
                f"  device {dev.mac_address} {dev.device_name!r} alive={dev.alive} rssi={dev.rssi}dBm "
                f"reverse_flow={dev.reverse_flow} fw={dev.firmware_version} esp={dev.status_esp}"
            )


def print_schedules(schedules: list, full: bool) -> None:
    """Print a summary of GET /schedules (or the raw JSON with --full)."""
    if full:
        print(json.dumps(schedules, indent=2))
        return
    for group in schedules:
        print(f"\nGroup {group.get('id')}: {group.get('name')!r} enable_schedule={group.get('enable_schedule')}")
        for item in group.get("schedules", []):
            repeat = item.get("repeat", {})
            action = item.get("action", {})
            meta = item.get("meta", {})
            header = item.get("header", {})
            when = f"{repeat.get('hour'):02d}:{repeat.get('minute'):02d}"
            print(
                f"  schedule_id={meta.get('schedule_id')} enabled={header.get('schedule_item_enabled')} "
                f"at={when} days={days_to_names(repeat.get('days', 0))} -> work_mode={action.get('work_mode')} "
                f"special_mode={action.get('special_mode')} last_modified={meta.get('last_modified')}"
            )


async def run_probe(args: argparse.Namespace) -> int:
    """Run the probe using the integration's own API client; return an exit code."""
    key = normalize_key(args.key)
    loc = str(args.loc).strip()
    base = args.base_url.rstrip("/")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            client = api.IVentApiClient(session, key, loc, base)
            if args.command == "info":
                info = await client.async_get_info()
                print(f"GET {base}/live/{loc}/info -> 200 OK")
                if args.full:
                    print(json.dumps(dataclasses.asdict(info), indent=2))
                else:
                    print_info(info)
                return 0
            if args.command == "schedules":
                schedules = await client.async_get_schedules()
                print(f"GET {base}/live/{loc}/schedules -> 200 OK")
                print_schedules(schedules, args.full)
                return 0
            # echo: verify the write path without changing anything
            info = await client.async_get_info()
            print(f"GET {base}/live/{loc}/info -> 200 OK")
            if not info.groups:
                print("No groups in this location; nothing to echo.")
                return 0
            group = info.groups[0]
            write = group.remote.to_write_dict()
            await client.async_modify_group(group.id, remote_work_mode=write)
            print(f"POST {base}/live/{loc}/modify_group group_id={group.id} -> 200 OK")
            print(f"echo of current values (no state change), remote_work_mode={json.dumps(write)}")
            print("write path OK")
            return 0
    except api.IVentAuthError as err:
        print(f"{err}")
        print(
            "authentication rejected (401/403): regenerate the API key in the i-Vent web UI and use "
            "the newest value in a fresh shell - regenerating revokes the old key, and a stale shell "
            "variable is a classic cause of this."
        )
        return 1
    except api.IVentNotFoundError as err:
        print(f"{err}")
        print(
            "location not found (404): check the loc_id - use the number from the web app's own "
            "/api/v1/live/<id>/info request."
        )
        return 1
    except api.IVentError as err:
        print(f"request failed: {err}")
        print("check network/DNS/proxy, or use --base-url to point at a local mock server.")
        return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
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
    return args


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    return asyncio.run(run_probe(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
