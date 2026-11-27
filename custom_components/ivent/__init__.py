"""The i-Vent Cloud integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IVentApiClient
from .const import CONF_LOC_ID, DAY_PRESETS, DOMAIN, MANUFACTURER, SpecialMode, WorkMode
from .coordinator import IVentCoordinator
from .entity import location_identifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_REMOVE_SCHEDULE = "remove_schedule"

ADD_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required("minute"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        vol.Required("days"): vol.In(list(DAY_PRESETS)),
        vol.Required("work_mode"): vol.In([mode.value for mode in WorkMode]),
        vol.Required("special_mode"): vol.In([mode.value for mode in SpecialMode]),
        vol.Optional("enabled", default=True): cv.boolean,
    }
)

REMOVE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("schedule_id"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up i-Vent Cloud from a config entry."""
    api = IVentApiClient(
        async_get_clientsession(hass), entry.data[CONF_API_KEY], entry.data[CONF_LOC_ID]
    )
    coordinator = IVentCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    _async_create_devices(hass, entry, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            _async_unregister_services(hass)
            hass.data.pop(DOMAIN)
    return unload_ok


def _async_create_devices(hass: HomeAssistant, entry: ConfigEntry, coordinator: IVentCoordinator) -> None:
    """Create the location, group and physical devices in the device registry."""
    device_registry = dr.async_get(hass)
    loc_identifier = location_identifier(coordinator.loc_id)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, loc_identifier)},
        name=f"i-Vent location {coordinator.loc_id}",
        manufacturer=MANUFACTURER,
    )
    for group in coordinator.groups:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(group.id))},
            name=group.name,
            manufacturer=MANUFACTURER,
            model="Ventilation group",
            via_device=(DOMAIN, loc_identifier),
        )
        for device in group.devices:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, device.mac_address)},
                name=device.device_name,
                manufacturer=MANUFACTURER,
                model="Ventilation device",
                sw_version=str(device.firmware_version),
                via_device=(DOMAIN, str(group.id)),
            )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _resolve_group(hass: HomeAssistant, device_id: str) -> tuple[IVentCoordinator, int]:
    """Resolve a HA device id to its coordinator and group id."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device {device_id}")
    entry_id = next((eid for eid in device.config_entries if eid in hass.data.get(DOMAIN, {})), None)
    if entry_id is None:
        raise HomeAssistantError("Selected device is not an i-Vent device")
    coordinator: IVentCoordinator = hass.data[DOMAIN][entry_id]
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.isdigit():
            return coordinator, int(identifier)
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            found = coordinator.get_device(identifier)
            if found is not None:
                return coordinator, found[0].id
    raise HomeAssistantError("Could not determine the i-Vent group for the selected device")


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the i-Vent services (once, shared by all entries)."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_SCHEDULE):
        return

    async def handle_add_schedule(call: ServiceCall) -> None:
        coordinator, group_id = _resolve_group(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_add_schedule(
            group_id,
            hour=int(call.data["hour"]),
            minute=int(call.data["minute"]),
            days=DAY_PRESETS[call.data["days"]],
            work_mode=call.data["work_mode"],
            special_mode=call.data["special_mode"],
            enabled=bool(call.data.get("enabled", True)),
        )

    async def handle_remove_schedule(call: ServiceCall) -> None:
        coordinator, group_id = _resolve_group(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_remove_schedule(group_id, int(call.data["schedule_id"]))

    hass.services.async_register(DOMAIN, SERVICE_ADD_SCHEDULE, handle_add_schedule, schema=ADD_SCHEDULE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_SCHEDULE, handle_remove_schedule, schema=REMOVE_SCHEDULE_SCHEMA
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the i-Vent services."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_SCHEDULE)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_SCHEDULE)
