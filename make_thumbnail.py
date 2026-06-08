"""
make_thumbnail.py — Generate a 1920x1080 branded placeholder thumbnail.
Run once: python make_thumbnail.py
Output: sample_data/thumbnail.jpg
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def make_thumbnail():
    width, height = 1920, 1080

    # Background gradient (dark navy to dark blue)
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Simple two-color gradient via horizontal bands
    for y in range(height):
        ratio = y / height
        r = int(10 + ratio * 5)
        g = int(17 + ratio * 10)
        b = int(40 + ratio * 30)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Accent bar at top
    draw.rectangle([(0, 0), (width, 8)], fill=(99, 179, 237))

    # Main title
    title = "AI Video Pipeline Demo"
    subtitle = "Script  →  ElevenLabs  →  HeyGen  →  FFmpeg  →  YouTube"

    # Try to load a system font; fall back to default
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 120)
        font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_tag = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_tag = font_title

    # White title text (centered)
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((width - tw) // 2, height // 2 - th - 40),
        title,
        font=font_title,
        fill=(255, 255, 255),
    )

    # Subtitle in light blue
    sbbox = draw.textbbox((0, 0), subtitle, font=font_sub)
    sw = sbbox[2] - sbbox[0]
    draw.text(
        ((width - sw) // 2, height // 2 + 40),
        subtitle,
        font=font_sub,
        fill=(147, 197, 253),
    )

    # Tag line
    tag = "Built with Claude Code"
    tbbox = draw.textbbox((0, 0), tag, font=font_tag)
    tw2 = tbbox[2] - tbbox[0]
    draw.text(
        ((width - tw2) // 2, height - 100),
        tag,
        font=font_tag,
        fill=(156, 163, 175),
    )

    out_path = Path(__file__).parent / "sample_data" / "thumbnail.jpg"
    img.save(out_path, "JPEG", quality=95)
    print(f"Thumbnail saved: {out_path}")


if __name__ == "__main__":
    make_thumbnail()
