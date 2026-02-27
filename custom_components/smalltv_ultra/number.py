"""SmallTV Ultra number entities – refresh and cycle intervals."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_REFRESH_INTERVAL,
    CONF_CYCLE_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_CYCLE_INTERVAL,
)
from .coordinator import SmallTVUltraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmallTVUltraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SmallTVRefreshIntervalNumber(coordinator, entry),
            SmallTVCycleIntervalNumber(coordinator, entry),
        ]
    )


class _SmallTVBaseNumber(CoordinatorEntity[SmallTVUltraCoordinator], NumberEntity):
    """Base class for SmallTV Ultra number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "s"

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})


class SmallTVRefreshIntervalNumber(_SmallTVBaseNumber):
    """How often (seconds) HA fetches camera images and uploads them.

    Stored in config entry options; changing it reloads the integration
    so the coordinator update_interval is applied immediately.
    """

    _attr_name = "Refresh Interval"
    _attr_native_min_value = 60
    _attr_native_max_value = 3600
    _attr_native_step = 1

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh_interval"

    @property
    def native_value(self) -> float:
        return float(
            self._entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        )

    async def async_set_native_value(self, value: float) -> None:
        new_options = {**self._entry.options, CONF_REFRESH_INTERVAL: int(value)}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        # The update_listener in __init__.py will reload the entry,
        # picking up the new update_interval.


class SmallTVCycleIntervalNumber(_SmallTVBaseNumber):
    """How many seconds between automatic image transitions on the device.

    Sent live to the device via /set?i_i=... and also persisted in options.
    """

    _attr_name = "Cycle Interval"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: SmallTVUltraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cycle_interval"

    @property
    def native_value(self) -> float:
        return float(
            self._entry.options.get(CONF_CYCLE_INTERVAL, DEFAULT_CYCLE_INTERVAL)
        )

    async def async_set_native_value(self, value: float) -> None:
        new_options = {**self._entry.options, CONF_CYCLE_INTERVAL: int(value)}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        # Also apply the new interval on the device immediately
        try:
            await self.coordinator.api.set_album_options(int(value), 1)
        except Exception:  # noqa: BLE001
            pass  # Not fatal – will be applied on next coordinator refresh
