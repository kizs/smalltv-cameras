"""Pillow-based image processing for SmallTV Ultra (240×240 IPS display)."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

# Candidate font paths (searched in order; first found wins)
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/config/custom_components/smalltv_ultra/DejaVuSans-Bold.ttf",
]
_FONT_SIZE = 20
_LABEL_BAR_HEIGHT = 30
_DISPLAY_SIZE = 240


def _load_font(font_path: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font, falling back gracefully to the built-in bitmap font."""
    candidates = ([font_path] if font_path else []) + _FONT_CANDIDATES
    for path in candidates:
        if path is None:
            continue
        try:
            return ImageFont.truetype(path, _FONT_SIZE)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _process_frame(
    raw_bytes: bytes,
    label: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None,
) -> Image.Image:
    """Return a 240×240 RGB PIL Image ready for export (JPEG or GIF frame)."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

    # Center crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Resize to display resolution
    img = img.resize((_DISPLAY_SIZE, _DISPLAY_SIZE), Image.LANCZOS)

    # Semi-transparent label bar at bottom (RGBA composite)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bar_top = _DISPLAY_SIZE - _LABEL_BAR_HEIGHT
    draw.rectangle([(0, bar_top), (_DISPLAY_SIZE, _DISPLAY_SIZE)], fill=(0, 0, 0, 160))

    if font is None:
        font = _load_font()
    text = label[:22]
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        ((_DISPLAY_SIZE - text_w) // 2, bar_top + (_LABEL_BAR_HEIGHT - text_h) // 2),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def process_camera_image(
    raw_bytes: bytes,
    label: str,
    font_path: str | None = None,
) -> bytes:
    """Return a 240×240 JPEG (used for single-image export / testing).

    CPU-bound – call via ``hass.async_add_executor_job()``.
    """
    out = io.BytesIO()
    _process_frame(raw_bytes, label, _load_font(font_path)).save(
        out, format="JPEG", quality=85, optimize=True
    )
    return out.getvalue()


def create_camera_gif(
    frames: list[tuple[bytes, str]],
    frame_duration_s: int = 3,
    font_path: str | None = None,
) -> bytes:
    """Build an animated GIF containing one frame per camera.

    Args:
        frames: list of (raw_image_bytes, label) tuples, one per camera.
        frame_duration_s: how long each frame is shown (seconds).
        font_path: optional custom font path.

    Returns GIF bytes.  CPU-bound – call via ``hass.async_add_executor_job()``.
    """
    font = _load_font(font_path)  # load once for all frames
    pil_frames: list[Image.Image] = []
    for raw_bytes, label in frames:
        pil_frames.append(_process_frame(raw_bytes, label, font))

    if not pil_frames:
        raise ValueError("No frames to encode")

    # Quantize each frame to 256-colour palette for GIF
    quantized = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT) for f in pil_frames]

    out = io.BytesIO()
    quantized[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=frame_duration_s * 1000,  # GIF uses milliseconds
        loop=0,                             # loop forever
        optimize=True,
    )
    return out.getvalue()
