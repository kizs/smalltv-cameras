"""SmallTV Ultra button entity – force immediate image refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmallTVUltraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmallTVUltraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmallTVForceRefreshButton(coordinator, entry)])


class SmallTVForceRefreshButton(
    CoordinatorEntity[SmallTVUltraCoordinator], ButtonEntity
):
    """Pressing this button triggers an immediate camera fetch + image upload."""

    _attr_has_entity_name = True
    _attr_name = "Force Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_force_refresh"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    async def async_press(self) -> None:
        """Handle button press – force coordinator refresh."""
        await self.coordinator.async_force_refresh()
