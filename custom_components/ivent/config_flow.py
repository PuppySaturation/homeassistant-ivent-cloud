"""Config flow for the i-Vent Cloud integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import IVentApiClient, IVentAuthError, IVentError, IVentNotFoundError, LiveInfo
from .const import (
    BASE_URL,
    CONF_BASE_URL,
    CONF_LOC_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_api_key(api_key: str) -> str:
    """Strip whitespace and an accidental 'Bearer ' prefix from the entered key."""
    key = api_key.strip()
    if key.lower().startswith("bearer "):
        key = key[len("bearer ") :].strip()
    return key


def _api_key_schema() -> vol.Schema:
    return vol.Schema(
        {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
    )


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_LOC_ID): NumberSelector(NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)),
            vol.Optional(CONF_BASE_URL, default=BASE_URL): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
        }
    )


class IVentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the i-Vent Cloud config flow."""

    VERSION = 1

    async def _async_validate(self, api_key: str, loc_id: int, base_url: str) -> LiveInfo:
        client = IVentApiClient(async_get_clientsession(self.hass), api_key, loc_id, base_url)
        return await client.async_get_info()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Ask for API key and location id, then validate against the cloud."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = _normalize_api_key(user_input[CONF_API_KEY])
            loc_id = int(user_input[CONF_LOC_ID])
            base_url = (user_input.get(CONF_BASE_URL) or BASE_URL).strip().rstrip("/") or BASE_URL
            await self.async_set_unique_id(str(loc_id))
            self._abort_if_unique_id_configured()
            try:
                info = await self._async_validate(api_key, loc_id, base_url)
            except IVentAuthError:
                errors["base"] = "invalid_auth"
            except IVentNotFoundError:
                errors["base"] = "invalid_location"
            except IVentError:
                errors["base"] = "cannot_connect"
            else:
                title = f"i-Vent location {loc_id}"
                if info.groups:
                    title += f" ({len(info.groups)} group{'s' if len(info.groups) != 1 else ''})"
                return self.async_create_entry(
                    title=title,
                    data={CONF_API_KEY: api_key, CONF_LOC_ID: loc_id, CONF_BASE_URL: base_url},
                )
        return self.async_show_form(step_id="user", data_schema=_user_schema(), errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> Any:
        """Start reauth flow when the API key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> Any:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None:
            api_key = _normalize_api_key(user_input[CONF_API_KEY])
            try:
                await self._async_validate(
                    api_key, entry.data[CONF_LOC_ID], entry.data.get(CONF_BASE_URL, BASE_URL)
                )
            except IVentAuthError:
                errors["base"] = "invalid_auth"
            except IVentError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_api_key_schema(),
            errors=errors,
            description_placeholders={"loc_id": str(entry.data[CONF_LOC_ID])},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> IVentOptionsFlow:
        """Return the options flow."""
        return IVentOptionsFlow()


class IVentOptionsFlow(OptionsFlow):
    """Handle i-Vent Cloud options (polling interval)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
