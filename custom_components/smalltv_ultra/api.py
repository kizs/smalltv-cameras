"""SmallTV Ultra HTTP API client."""
from __future__ import annotations

from typing import Any

import aiohttp


class SmallTVApiError(Exception):
    """Raised when a SmallTV Ultra API call fails."""


class SmallTVApi:
    """Async HTTP client for the SmallTV Ultra stock firmware API."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        self._base = f"http://{host}"

    # ------------------------------------------------------------------ #
    # Status / info                                                        #
    # ------------------------------------------------------------------ #

    async def get_info(self) -> dict[str, Any]:
        """GET /v.json → {"m": "SmallTV-Ultra", "v": "Ultra-V9.0.45"}."""
        return await self._get_json("/v.json")

    async def get_app_info(self) -> dict[str, Any]:
        """GET /app.json → {"theme": 3}."""
        return await self._get_json("/app.json")

    async def get_album_info(self) -> dict[str, Any]:
        """GET /album.json → {"autoplay": 1, "i_i": 5}."""
        return await self._get_json("/album.json")

    async def get_storage(self) -> dict[str, Any]:
        """GET /space.json → {"total": ..., "free": ...} (bytes)."""
        return await self._get_json("/space.json")

    # ------------------------------------------------------------------ #
    # Settings  (GET /set?...)                                             #
    # ------------------------------------------------------------------ #

    async def set_theme(self, n: int) -> None:
        """Switch to theme n (3 = Photo Album – required for image display)."""
        await self._set(theme=n)

    async def set_image(self, path: str) -> None:
        """Display a specific image.  path example: /image//cam1.jpg"""
        await self._set(img=path)

    async def set_brightness(self, value: int) -> None:
        """Set display brightness 0-100."""
        await self._set(brt=value)

    async def set_album_options(self, i_i: int, autoplay: int) -> None:
        """Configure photo album: i_i = cycle interval (s), autoplay 0/1."""
        await self._set(i_i=i_i, autoplay=autoplay)

    async def set_gif(self, path: str) -> None:
        """Display a GIF file.  path example: /image//cameras.gif"""
        await self._set(gif=path)

    async def clear_images(self) -> None:
        """Delete all images in /image/ on the device."""
        await self._set(clear="image")

    # ------------------------------------------------------------------ #
    # File management                                                      #
    # ------------------------------------------------------------------ #

    async def upload_image(
        self, filename: str, data: bytes, content_type: str = "image/jpeg"
    ) -> None:
        """POST /doUpload?dir=/image/ – upload an image file (JPEG or GIF).

        Builds the multipart body manually to avoid the aiohttp FormData
        bug that emits a duplicate Content-Length header, which the ESP8266
        rejects with HTTP 400.
        """
        boundary = "----SmallTVBoundary7MA4YWxkTrZu0gW"
        part_header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n"
        ).encode()
        body = part_header + data + f"\r\n--{boundary}--\r\n".encode()

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        try:
            async with self._session.post(
                f"{self._base}/doUpload?dir=/image/",
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise SmallTVApiError(
                        f"Upload '{filename}' failed with HTTP {resp.status}"
                    )
        except aiohttp.ClientResponseError as exc:
            # The ESP8266 firmware sends a malformed HTTP response with duplicate
            # Content-Length headers.  Newer aiohttp raises a synthetic 400 error
            # when it encounters this, even though the upload succeeded on the
            # device.  Treat this specific case as success.
            if "Duplicate Content-Length" not in str(exc):
                raise SmallTVApiError(f"Upload request error: {exc}") from exc
        except aiohttp.ClientError as exc:
            raise SmallTVApiError(f"Upload request error: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                f"{self._base}{path}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise SmallTVApiError(
                        f"GET {path} returned HTTP {resp.status}"
                    )
                # content_type=None: device may return text/plain
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise SmallTVApiError(f"Request error for {path}: {exc}") from exc

    async def _set(self, **params: Any) -> None:
        """Call GET /set?key=value&... and assert HTTP 200."""
        str_params = {k: str(v) for k, v in params.items()}
        try:
            async with self._session.get(
                f"{self._base}/set",
                params=str_params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise SmallTVApiError(
                        f"GET /set?{str_params} returned HTTP {resp.status}"
                    )
        except aiohttp.ClientError as exc:
            raise SmallTVApiError(f"Request error for /set: {exc}") from exc
