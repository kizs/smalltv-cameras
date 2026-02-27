"""SmallTV Ultra select entity – display mode (cameras / builtin)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_MODE,
    DEFAULT_MODE,
    MODE_CAMERAS,
    MODE_BUILTIN,
)
from .coordinator import SmallTVUltraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmallTVUltraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmallTVDisplayModeSelect(coordinator, entry)])


class SmallTVDisplayModeSelect(
    CoordinatorEntity[SmallTVUltraCoordinator], SelectEntity
):
    """Switch between camera slideshow and built-in firmware themes."""

    _attr_has_entity_name = True
    _attr_name = "Display Mode"
    _attr_icon = "mdi:television-play"
    _attr_options = [MODE_CAMERAS, MODE_BUILTIN]

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_display_mode"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    @property
    def current_option(self) -> str:
        return self._entry.options.get(CONF_MODE, DEFAULT_MODE)

    async def async_select_option(self, option: str) -> None:
        """Apply the new mode: flip the firmware theme, then re-trigger the coordinator."""
        new_options = {**self._entry.options, CONF_MODE: option}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

        try:
            if option == MODE_CAMERAS:
                # Switch device to Photo Album so images can be displayed
                await self.coordinator.api.set_theme(3)
            else:
                # Revert to Weather Clock Today (theme 1) as the default builtin
                await self.coordinator.api.set_theme(1)
        except Exception:  # noqa: BLE001
            pass  # Best-effort; coordinator will handle state on next refresh

        await self.coordinator.async_force_refresh()
