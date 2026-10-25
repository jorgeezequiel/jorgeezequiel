#!/usr/bin/env python3
"""Render a polished, GitHub-compatible animated profile-name banner with Pillow."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "jorge-ezequiel-animated.gif"
WIDTH, HEIGHT = 1000, 210
FRAMES, DURATION = 36, 95
NAVY = (7, 13, 27)
PANEL = (11, 20, 38)
MUTED = (139, 157, 181)
CYAN = (56, 189, 248)
VIOLET = (167, 139, 250)
TEAL = (45, 212, 191)


def font_path(bold: bool = False) -> str:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if Path(path).is_file():
            return path
    raise RuntimeError("A TrueType font is required to render the profile banner.")


def mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float):
    stops = [(0.0, CYAN), (0.48, VIOLET), (1.0, TEAL)]
    t %= 1.0
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


def make_background(phase: float) -> Image.Image:
    """Draw a quiet, high-contrast panel with soft ambient color, not a flat box."""
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            nx = (x - WIDTH * 0.5) / (WIDTH * 0.65)
            ny = (y - HEIGHT * 0.45) / (HEIGHT * 0.8)
            glow_cyan = max(0.0, 1.0 - math.sqrt((nx + 0.38) ** 2 + ny ** 2)) * 0.18
            glow_violet = max(0.0, 1.0 - math.sqrt((nx - 0.25) ** 2 + (ny + 0.1) ** 2)) * 0.16
            base = tuple(int(NAVY[i] + (CYAN[i] - NAVY[i]) * glow_cyan
                             + (VIOLET[i] - NAVY[i]) * glow_violet) for i in range(3))
            pixels[x, y] = base

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, WIDTH - 13, HEIGHT - 13), radius=22,
                           outline=(37, 55, 81), width=1)
    draw.rounded_rectangle((17, 17, WIDTH - 18, HEIGHT - 18), radius=18,
                           outline=(19, 36, 59), width=1)

    # Restrained corner details and tiny background points add structure without clutter.
    draw.line((38, 45, 38, 70), fill=(50, 83, 112), width=2)
    draw.line((38, 45, 63, 45), fill=(50, 83, 112), width=2)
    draw.line((WIDTH - 39, HEIGHT - 45, WIDTH - 39, HEIGHT - 70),
              fill=(50, 83, 112), width=2)
    draw.line((WIDTH - 39, HEIGHT - 45, WIDTH - 64, HEIGHT - 45),
              fill=(50, 83, 112), width=2)
    for i in range(18):
        x = 78 + i * 49
        y = 36 + (i % 3) * 8
        alpha = 75 + int(40 * (0.5 + 0.5 * math.sin(phase * 2 * math.pi + i)))
        draw.ellipse((x, y, x + 2, y + 2), fill=(alpha // 2, alpha, alpha))
    return image


def render_frame(index: int, name_font, label_font) -> Image.Image:
    phase = index / FRAMES
    image = make_background(phase).convert("RGBA")
    name = "Jorge Ezequiel"
    name_bbox = name_font.getbbox(name)
    name_width = name_bbox[2] - name_bbox[0]
    x = (WIDTH - name_width) // 2 - name_bbox[0]
    float_y = round(math.sin(phase * 2 * math.pi) * 1.5)
    y = 67 + float_y - name_bbox[1]

    # Gradient text is painted through a text mask, with a subtle glow underneath.
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    md = ImageDraw.Draw(mask)
    md.text((x, y), name, font=name_font, fill=255)
    glow_mask = mask.filter(ImageFilter.GaussianBlur(10))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (*CYAN, 0))
    glow.putalpha(glow_mask.point(lambda value: int(value * 0.20)))
    image = Image.alpha_composite(image, glow)

    gradient = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gp = gradient.load()
    mp = mask.load()
    for px in range(WIDTH):
        color = gradient_color((px / WIDTH * 0.78 + phase * 0.48) % 1.0)
        for py in range(HEIGHT):
            if mp[px, py]:
                gp[px, py] = (*color, 255)
    image = Image.alpha_composite(image, gradient)

    draw = ImageDraw.Draw(image)
    label = ""
    label_bbox = draw.textbbox((0, 0), label, font=label_font)
    label_width = label_bbox[2] - label_bbox[0]
    draw.text(((WIDTH - label_width) // 2, 42), label, font=label_font,
              fill=(*MUTED, 255))

    # The name stays clean: no moving dot or animated underline beneath it.

    # Tiny bottom caption anchors the composition without competing with the name.
    caption = ""
    cb = draw.textbbox((0, 0), caption, font=label_font)
    draw.text(((WIDTH - (cb[2] - cb[0])) // 2, 170), caption,
              font=label_font, fill=(103, 123, 150, 255))
    return image


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    name_font = ImageFont.truetype(font_path(True), 68)
    label_font = ImageFont.truetype(font_path(False), 12)
    rendered = [render_frame(i, name_font, label_font) for i in range(FRAMES)]

    # Use one global palette so colors remain stable between frames.
    rgb_frames = [frame.convert("RGB") for frame in rendered]
    palette_reference = rgb_frames[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    indexed = [
        frame.quantize(palette=palette_reference, dither=Image.Dither.NONE)
        for frame in rgb_frames
    ]
    indexed[0].save(
        OUTPUT, format="GIF", save_all=True, append_images=indexed[1:],
        duration=DURATION, loop=0, optimize=False, disposal=2,
    )
    with Image.open(OUTPUT) as check:
        if check.format != "GIF" or check.n_frames != FRAMES or check.size != (WIDTH, HEIGHT):
            raise RuntimeError("Generated banner failed GIF validation.")
    print(f"Generated {OUTPUT.relative_to(ROOT)}: {WIDTH}x{HEIGHT}, {FRAMES} frames.")


if __name__ == "__main__":
    main()
