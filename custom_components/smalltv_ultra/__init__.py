"""SmallTV Ultra – Home Assistant custom integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmallTVApi, SmallTVApiError
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    PLATFORMS,
)
from .coordinator import SmallTVUltraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmallTV Ultra from a config entry."""
    host: str = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    api = SmallTVApi(host, session)

    # Verify the device is reachable before proceeding
    try:
        await api.get_info()
    except SmallTVApiError as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to SmallTV Ultra at {host}: {err}"
        ) from err

    refresh_interval: int = int(
        entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
    )

    coordinator = SmallTVUltraCoordinator(
        hass=hass,
        api=api,
        entry=entry,
        update_interval=timedelta(seconds=refresh_interval),
    )

    # Perform first refresh (raises ConfigEntryNotReady on failure)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options change (new cameras / intervals / mode)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
