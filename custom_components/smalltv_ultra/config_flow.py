"""Config flow for SmallTV Ultra integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import SmallTVApi, SmallTVApiError
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_CAMERAS,
    CONF_REFRESH_INTERVAL,
    CONF_CYCLE_INTERVAL,
    CONF_MODE,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_CYCLE_INTERVAL,
    DEFAULT_MODE,
    MODE_CAMERAS,
    MODE_BUILTIN,
)


class SmallTVUltraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmallTV Ultra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step – ask for IP address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            api = SmallTVApi(host, session)
            try:
                info = await api.get_info()
                model = info.get("m", "")
                if "SmallTV-Ultra" not in model:
                    errors["base"] = "not_smalltv_ultra"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"SmallTV Ultra ({host})",
                        data={CONF_HOST: host},
                    )
            except (aiohttp.ClientError, SmallTVApiError, TimeoutError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmallTVUltraOptionsFlow:
        return SmallTVUltraOptionsFlow()


class SmallTVUltraOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing SmallTV Ultra entry."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        current_cameras: list[str] = opts.get(CONF_CAMERAS, [])
        current_refresh: int = opts.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        current_cycle: int = opts.get(CONF_CYCLE_INTERVAL, DEFAULT_CYCLE_INTERVAL)
        current_mode: str = opts.get(CONF_MODE, DEFAULT_MODE)

        schema = vol.Schema(
            {
                vol.Optional(CONF_CAMERAS, default=current_cameras): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="camera", multiple=True)
                ),
                vol.Optional(
                    CONF_REFRESH_INTERVAL, default=current_refresh
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=3600, step=1, unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_CYCLE_INTERVAL, default=current_cycle
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10, step=1, unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_MODE, default=current_mode): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[MODE_CAMERAS, MODE_BUILTIN],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="display_mode",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
