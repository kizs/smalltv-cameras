"""Config flow for SmallTV Ultra integration."""
from __future__ import annotations

import asyncio
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

_SCAN_TIMEOUT = aiohttp.ClientTimeout(total=2)
_SCAN_CONCURRENCY = 50


class SmallTVUltraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmallTV Ultra."""

    VERSION = 1

    def __init__(self) -> None:
        self._found: list[tuple[str, str]] = []  # (ip, firmware_version)

    # ------------------------------------------------------------------ #
    # Step 1 – choose method                                               #
    # ------------------------------------------------------------------ #

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask whether to scan the network or enter an IP manually."""
        if user_input is not None:
            if user_input["method"] == "scan":
                return await self.async_step_scan()
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="scan"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["scan", "manual"],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="add_method",
                        )
                    )
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 2a – scan                                                       #
    # ------------------------------------------------------------------ #

    async def async_step_scan(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask for subnet prefix, then scan all 254 hosts concurrently."""
        errors: dict[str, str] = {}

        if user_input is not None:
            subnet = user_input["subnet"].strip().rstrip(".")
            self._found = await self._async_scan_subnet(subnet)
            if not self._found:
                errors["base"] = "no_devices_found"
            else:
                return await self.async_step_pick()

        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {vol.Required("subnet", default="192.168.0"): str}
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Step 2b – pick from found devices                                    #
    # ------------------------------------------------------------------ #

    async def async_step_pick(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Let the user pick one of the discovered SmallTV Ultra devices."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            fw = next((v for ip, v in self._found if ip == host), "")
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"SmallTV Ultra ({host})",
                data={CONF_HOST: host},
            )

        options = [
            selector.SelectOptionDict(value=ip, label=f"{ip}  –  {fw}")
            for ip, fw in sorted(self._found)
        ]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 2c – manual IP entry                                            #
    # ------------------------------------------------------------------ #

    async def async_step_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manual IP address entry with validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            api = SmallTVApi(host, session)
            try:
                info = await api.get_info()
                if "SmallTV-Ultra" not in info.get("m", ""):
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
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Reconfigure (change IP of existing entry)                            #
    # ------------------------------------------------------------------ #

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle IP address change for an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            api = SmallTVApi(host, session)
            try:
                info = await api.get_info()
                if "SmallTV-Ultra" not in info.get("m", ""):
                    errors["base"] = "not_smalltv_ultra"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=f"SmallTV Ultra ({host})",
                        data={CONF_HOST: host},
                    )
            except (aiohttp.ClientError, SmallTVApiError, TimeoutError):
                errors["base"] = "cannot_connect"

        current_host = self._get_reconfigure_entry().data.get(CONF_HOST, "")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=current_host): str}
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Options flow                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmallTVUltraOptionsFlow:
        return SmallTVUltraOptionsFlow()

    # ------------------------------------------------------------------ #
    # Subnet scanner                                                       #
    # ------------------------------------------------------------------ #

    async def _async_scan_subnet(self, subnet: str) -> list[tuple[str, str]]:
        """Probe subnet.1–254 concurrently; return [(ip, firmware_version)]."""
        session = async_get_clientsession(self.hass)
        sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

        async def probe(ip: str) -> tuple[str, str] | None:
            async with sem:
                try:
                    async with session.get(
                        f"http://{ip}/v.json",
                        timeout=_SCAN_TIMEOUT,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if "SmallTV-Ultra" in data.get("m", ""):
                                return ip, data.get("v", "unknown")
                except Exception:
                    pass
            return None

        results = await asyncio.gather(
            *[probe(f"{subnet}.{i}") for i in range(1, 255)]
        )
        return [r for r in results if r is not None]


# --------------------------------------------------------------------------- #
# Options flow                                                                 #
# --------------------------------------------------------------------------- #

class SmallTVUltraOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing SmallTV Ultra entry."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
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
