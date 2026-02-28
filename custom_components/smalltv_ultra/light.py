"""SmallTV Ultra light entity – controls display brightness."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST
from .coordinator import SmallTVUltraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmallTVUltraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmallTVUltraLight(coordinator, entry)])


class SmallTVUltraLight(CoordinatorEntity[SmallTVUltraCoordinator], LightEntity):
    """Represents the SmallTV Ultra display as a dimmable light in HA."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
    _attr_has_entity_name = True
    _attr_translation_key = "brightness"
    _attr_name = "Brightness"

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_brightness"
        # Track state locally; the device has no endpoint to read brightness back
        self._brightness: int = 255   # HA scale 0-255
        self._is_on: bool = True

    @property
    def device_info(self) -> DeviceInfo:
        model = "SmallTV Pro" if self.coordinator.is_pro else "SmallTV Ultra"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=model,
            manufacturer="GeekMagic",
            model=model,
            sw_version=self.coordinator.firmware_version,
            configuration_url=f"http://{self._entry.data[CONF_HOST]}",
        )

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    async def async_turn_on(self, **kwargs) -> None:
        ha_brt: int = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        # Map HA 0-255 → device 0-100
        device_brt = round(ha_brt / 255 * 100)
        await self.coordinator.api.set_brightness(device_brt)
        self._brightness = ha_brt
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.api.set_brightness(0)
        self._is_on = False
        self.async_write_ha_state()
