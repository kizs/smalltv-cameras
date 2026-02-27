"""DataUpdateCoordinator for SmallTV Ultra."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmallTVApi, SmallTVApiError
from .const import (
    DOMAIN,
    CONF_CAMERAS,
    CONF_CYCLE_INTERVAL,
    CONF_MODE,
    DEFAULT_CYCLE_INTERVAL,
    DEFAULT_MODE,
    MODE_CAMERAS,
    MODE_BUILTIN,
)
from . import image_processor

_LOGGER = logging.getLogger(__name__)


class SmallTVUltraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages periodic image upload and state tracking for a SmallTV Ultra device."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SmallTVApi,
        entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        self.api = api
        self.entry = entry
        self._firmware_version: str = "unknown"
        # Flag: True means we need to (re-)send theme + album settings on next run
        self._needs_album_init: bool = True

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    @property
    def firmware_version(self) -> str:
        return self._firmware_version

    # ------------------------------------------------------------------ #
    # Core update                                                          #
    # ------------------------------------------------------------------ #

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data / push images.  Called by HA on every interval."""
        # Always fetch device info so we have the firmware version
        try:
            info = await self.api.get_info()
            self._firmware_version = info.get("v", "unknown")
        except SmallTVApiError as err:
            raise UpdateFailed(f"Cannot reach SmallTV Ultra: {err}") from err

        opts = self.entry.options
        mode: str = opts.get(CONF_MODE, DEFAULT_MODE)
        cycle_interval: int = int(opts.get(CONF_CYCLE_INTERVAL, DEFAULT_CYCLE_INTERVAL))
        cameras: list[str] = opts.get(CONF_CAMERAS, [])

        if mode == MODE_BUILTIN:
            try:
                app_info = await self.api.get_app_info()
            except SmallTVApiError as err:
                raise UpdateFailed(f"Cannot get app info: {err}") from err
            self._needs_album_init = True  # Re-init next time we switch to cameras
            return {"mode": MODE_BUILTIN, "theme": app_info.get("theme", 1)}

        # ---- MODE_CAMERAS ----
        if not cameras:
            _LOGGER.debug("No cameras configured – skipping upload")
            return {"mode": MODE_CAMERAS, "cameras": []}

        # Collect raw frames from all configured cameras
        frames: list[tuple[bytes, str]] = []
        for entity_id in cameras:
            try:
                img_obj = await async_get_image(self.hass, entity_id)
                label = entity_id.split(".", 1)[-1].replace("_", " ")
                frames.append((img_obj.content, label))
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to fetch camera '%s': %s", entity_id, err)

        if not frames:
            _LOGGER.debug("No camera frames available – skipping upload")
            return {"mode": MODE_CAMERAS, "cameras": []}

        # Build animated GIF in thread executor (CPU-bound)
        try:
            gif_bytes: bytes = await self.hass.async_add_executor_job(
                image_processor.create_camera_gif,
                frames,
                cycle_interval,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to create GIF: %s", err)
            return {"mode": MODE_CAMERAS, "cameras": []}

        _LOGGER.debug(
            "Created GIF: %d frames, %d bytes, %ds/frame",
            len(frames), len(gif_bytes), cycle_interval,
        )

        # On first run (or after mode switch): switch to Photo Album and clear old files
        if self._needs_album_init:
            try:
                await self.api.set_theme(3)
                await self.api.clear_images()
                _LOGGER.debug("Switched to Photo Album mode, cleared old images")
            except SmallTVApiError as err:
                _LOGGER.warning("Failed to initialise GIF mode: %s", err)

        # Upload the GIF and tell the device to display it
        try:
            await self.api.upload_image("cameras.gif", gif_bytes, content_type="image/gif")
            await self.api.set_gif("/image//cameras.gif")
            self._needs_album_init = False
            _LOGGER.debug("GIF uploaded and displayed")
        except SmallTVApiError as err:
            _LOGGER.warning("Failed to upload/display GIF: %s", err)

        return {"mode": MODE_CAMERAS, "cameras": [label for _, label in frames]}

    # ------------------------------------------------------------------ #
    # Public helpers (called by entity platforms)                          #
    # ------------------------------------------------------------------ #

    async def async_force_refresh(self) -> None:
        """Trigger an immediate update (e.g. from Force Refresh button)."""
        self._needs_album_init = True
        await self.async_refresh()
