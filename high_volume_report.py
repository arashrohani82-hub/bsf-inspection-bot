"""Memory-conscious image embedding for very large inspection reports.

The original inspection photographs remain untouched.  Only the temporary JPEG
inserted into Word is resized/compressed so reports with hundreds of photographs
can be generated within modest Railway memory limits.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import inspection_bot as bot

log = logging.getLogger(__name__)


def _font(font_size: int):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), font_size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def _optimized_labelled_image(
    img_path,
    label,
    output_path,
    display_width_px=800,
):
    """Create a small report-only JPEG with the figure label baked in."""
    target_width = min(max(int(display_width_px or 800), 700), 900)

    with Image.open(img_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        if image.width > target_width:
            ratio = target_width / float(image.width)
            target_height = max(1, int(image.height * ratio))
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            image = image.copy()

    draw = ImageDraw.Draw(image)
    font_size = max(28, min(42, int(image.width * 0.045)))
    font = _font(font_size)
    margin = max(7, font_size // 6)
    pad = max(5, font_size // 8)
    bbox = draw.textbbox((0, 0), str(label), font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    box = [
        margin,
        margin,
        margin + width + 2 * pad,
        margin + height + 2 * pad,
    ]
    draw.rectangle(box, fill="white", outline="black", width=2)
    draw.text(
        (margin + pad - bbox[0], margin + pad - bbox[1]),
        str(label),
        fill="black",
        font=font,
    )

    # 70% JPEG quality is visually sufficient for a 2.7-inch report image and
    # reduces embedded size dramatically versus the previous quality=92 output.
    image.save(
        output_path,
        format="JPEG",
        quality=70,
        optimize=True,
        progressive=False,
        dpi=(150, 150),
    )
    image.close()
    return output_path


def install_high_volume_report() -> None:
    bot.add_label_to_image = _optimized_labelled_image
    log.info("High-volume report image optimization enabled")
