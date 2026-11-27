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

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest
```
