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
    CONF_DEVICE_TYPE,
    DEVICE_ULTRA,
    DEVICE_PRO,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_CYCLE_INTERVAL,
    DEFAULT_MODE,
    MODE_CAMERAS,
    MODE_BUILTIN,
)


def _device_type(model: str) -> str | None:
    """Return DEVICE_ULTRA / DEVICE_PRO based on /v.json model string, or None."""
    if "SmallTV-Ultra" in model:
        return DEVICE_ULTRA
    if "SmallTV-PRO" in model or "SmallTV Pro" in model:
        return DEVICE_PRO
    return None

_SCAN_TIMEOUT = aiohttp.ClientTimeout(total=2)
_SCAN_CONCURRENCY = 50


class SmallTVUltraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmallTV Ultra."""

    VERSION = 1

    def __init__(self) -> None:
        self._found: list[tuple[str, str, str]] = []  # (ip, firmware_version, device_type)

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
        """Let the user pick one of the discovered SmallTV devices."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            entry = next((t for t in self._found if t[0] == host), None)
            fw, dtype = (entry[1], entry[2]) if entry else ("", DEVICE_ULTRA)
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            model_name = "SmallTV Pro" if dtype == DEVICE_PRO else "SmallTV Ultra"
            return self.async_create_entry(
                title=f"{model_name} ({host})",
                data={CONF_HOST: host, CONF_DEVICE_TYPE: dtype},
            )

        options = [
            selector.SelectOptionDict(
                value=ip,
                label=f"{ip}  –  {'Pro' if dtype == DEVICE_PRO else 'Ultra'}  {fw}",
            )
            for ip, fw, dtype in sorted(self._found)
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
                dtype = _device_type(info.get("m", ""))
                if dtype is None:
                    errors["base"] = "not_smalltv_ultra"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    model_name = "SmallTV Pro" if dtype == DEVICE_PRO else "SmallTV Ultra"
                    return self.async_create_entry(
                        title=f"{model_name} ({host})",
                        data={CONF_HOST: host, CONF_DEVICE_TYPE: dtype},
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
                dtype = _device_type(info.get("m", ""))
                if dtype is None:
                    errors["base"] = "not_smalltv_ultra"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    model_name = "SmallTV Pro" if dtype == DEVICE_PRO else "SmallTV Ultra"
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=f"{model_name} ({host})",
                        data={CONF_HOST: host, CONF_DEVICE_TYPE: dtype},
                        unique_id=host,
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

    async def _async_scan_subnet(self, subnet: str) -> list[tuple[str, str, str]]:
        """Probe subnet.1–254 concurrently; return [(ip, firmware_version, device_type)]."""
        session = async_get_clientsession(self.hass)
        sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

        async def probe(ip: str) -> tuple[str, str, str] | None:
            async with sem:
                try:
                    async with session.get(
                        f"http://{ip}/v.json",
                        timeout=_SCAN_TIMEOUT,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            dtype = _device_type(data.get("m", ""))
                            if dtype is not None:
                                return ip, data.get("v", "unknown"), dtype
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
