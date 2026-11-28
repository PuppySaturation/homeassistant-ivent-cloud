# i-Vent Cloud for Home Assistant

Custom [Home Assistant](https://www.home-assistant.io/) integration for **i-Vent** ventilation
systems, built on the i-Vent Smart Home Cloud API (`https://cloud.i-vent.com/api/v1`).

## Features

- One config entry per i-Vent location (`loc_id`) — add multiple locations
- Polling of the full system state (`GET /live/{loc_id}/info`) via a data update coordinator
- Each ventilation **group** is a Home Assistant device with:
  - a **fan** entity (on/off, 3 speeds as percentages, preset modes: On, Custom, Recuperation 1–3, Bypass 1–3)
  - **select** entities for special mode (Boost / Snooze / Night 1 / Night 2), bypass rotation,
    remote control mode (Normal / Bypass), LED mode and buzzer mode
  - a **switch** to enable/disable schedules, plus full **schedule editing**: time, days,
    work mode, special mode and per-item enable, and `ivent.add_schedule` / `ivent.remove_schedule` services
  - a timestamp sensor for when the current special mode ends
- Each physical device (MAC) is a sub-device with signal strength (RSSI), firmware version,
  ESP status, online (connectivity) binary sensor and a **reverse flow** switch

## Installation (HACS)

1. Add this repository as a custom repository in HACS (category: Integration)
2. Install **i-Vent Cloud** and restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → i-Vent Cloud**
4. Enter your **API key** (Bearer token from your i-Vent account) and your **location ID** (`loc_id`)

## Testing the API locally (outside Home Assistant)

`scripts/ivent_api_probe.py` is a small diagnostic script that calls the cloud API
directly — useful to verify your key/loc_id before involving HA.

**Requirements:** Python 3.11+ only. The script uses just the standard library, so
**no virtualenv and no `pip install` are needed** — any machine with Python works:

```bash
python3 --version   # needs 3.11+
```

(If you prefer isolation: `python3 -m venv .venv && source .venv/bin/activate` — nothing extra to install either.)

**Usage** — set the credentials as environment variables in the *same* shell you run the
script from (use `read -s` to type them so they don't land in shell history; a stale
variable from an earlier shell is a classic source of 401s after regenerating the key):

```bash
read -s IVENT_API_KEY   # paste the API key from the i-Vent web UI
read -s IVENT_LOC_ID    # paste the location id

python3 scripts/ivent_api_probe.py info        # system state (groups, devices, modes)
python3 scripts/ivent_api_probe.py schedules   # weekly schedules
python3 scripts/ivent_api_probe.py echo        # write-path test: POSTs the current values unchanged
python3 scripts/ivent_api_probe.py info --full # raw JSON
```

Or pass them directly (note: this lands in shell history):

```bash
python3 scripts/ivent_api_probe.py --key "$IVENT_API_KEY" --loc "$IVENT_LOC_ID" info
```

`--base-url` (or `IVENT_BASE_URL`) overrides the API host, e.g. to point at a local mock.
The script prints the request URL and HTTP status, a summary of the response, and exits
non-zero on errors — so it works well in CI-style one-liners too.

**Reading the output:**

| Symptom | Meaning | Fix |
|---|---|---|
| `HTTP 401/403` + "authentication rejected" | key wrong/revoked | regenerate in the i-Vent web UI; use the newest key in a fresh shell |
| `HTTP 404` + "location not found" | wrong `loc_id` | use the number from the web app's own `/api/v1/live/<id>/info` request |
| `connection error` | network/DNS/proxy | check connectivity, VPN, proxy |
| `HTTP 200` | all good | proceed to add the integration in HA |

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest
```
