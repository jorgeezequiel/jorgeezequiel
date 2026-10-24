#!/usr/bin/env python3
"""Generate a GitHub-README-safe animated name banner as a real GIF.

Uses Pillow only; unlike animated SVG, each motion frame is rasterized into the
GIF, so GitHub's SVG sanitization/proxy cannot freeze the name animation.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "jorge-ezequiel-animated.gif"
WIDTH, HEIGHT = 1000, 190
FRAMES, DURATION = 36, 90


def font_path() -> str:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    )
    for path in candidates:
        if Path(path).is_file():
            return path
    raise RuntimeError("A bold TrueType font is required to render the banner.")


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float):
    stops = [
        (0.0, (56, 189, 248)),
        (0.5, (167, 139, 250)),
        (1.0, (45, 212, 191)),
    ]
    t = t % 1.0
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


def render_frame(index: int, font: ImageFont.FreeTypeFont):
    phase = index / FRAMES
    frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    text = "Jorge Ezequiel"
    bbox = font.getbbox(text, stroke_width=0)
    text_width = bbox[2] - bbox[0]
    x = (WIDTH - text_width) // 2 - bbox[0]
    float_y = round(math.sin(phase * 2 * math.pi) * 2)
    y = 39 + float_y - bbox[1]

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    md = ImageDraw.Draw(mask)
    md.text((x, y), text, font=font, fill=255, stroke_width=0)

    # Soft, restrained glow behind the gradient lettering.
    glow_mask = mask.filter(ImageFilter.GaussianBlur(7))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (56, 189, 248, 0))
    glow.putalpha(glow_mask.point(lambda p: int(p * 0.24)))
    frame = Image.alpha_composite(frame, glow)

    gradient = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pixels = gradient.load()
    sweep = phase
    for px in range(WIDTH):
        # Move the color gradient slowly across the name.
        c = gradient_color((px / WIDTH * 0.72 + sweep * 0.55) % 1.0)
        for py in range(HEIGHT):
            if mask.getpixel((px, py)):
                pixels[px, py] = (*c, 255)
    frame = Image.alpha_composite(frame, gradient)

    # Animated curved underline: a bright highlight travels along the stroke.
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    left, right = (WIDTH - 360) // 2, (WIDTH + 360) // 2
    points = []
    for step in range(181):
        t = step / 180
        px = left + (right - left) * t
        py = 137 + 8 * math.sin(t * math.pi) + float_y * 0.15
        points.append((round(px), round(py)))
    d.line(points, fill=(100, 116, 139, 100), width=2)
    highlight = phase
    for step in range(181):
        t = step / 180
        px, py = points[step]
        distance = abs(t - highlight)
        if distance > 0.18:
            # Loop across the underline with a short glowing head.
            distance = min(distance, abs(t - (highlight - 1)), abs(t - (highlight + 1)))
        alpha = max(0, int(230 * (1 - distance / 0.18))) if distance <= 0.18 else 0
        if alpha:
            d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(45, 212, 191, alpha))
    frame = Image.alpha_composite(frame, overlay)

    # Convert to palette mode with transparency retained for GitHub's page theme.
    return frame


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(font_path(), 70)
    frames = [render_frame(i, font) for i in range(FRAMES)]
    # Use a shared palette to avoid flicker between frames.
    rgb_frames = [frame.convert("RGB") for frame in frames]
    palette_reference = rgb_frames[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    palette = palette_reference.getpalette()
    indexed = []
    for frame in rgb_frames:
        q = frame.quantize(palette=palette_reference, dither=Image.Dither.NONE)
        indexed.append(q)
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
