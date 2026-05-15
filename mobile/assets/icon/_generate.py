"""Generate Luma app icons from the live-site brand mark.

The marketing site (static/css/app.css `.brand-mark`) shows the brand as a
rounded square filled with a 135° gradient from #14b8a6 → #0f766e, glowing
on a #0F172A navy background. This script reproduces that at icon scale
(1024×1024) plus an adaptive-Android foreground that respects the 66% safe
zone.

Re-run after a brand tweak:
    .venv/bin/python mobile/assets/icon/_generate.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent

# Brand tokens (lifted from static/css/app.css)
NAVY = (15, 23, 42)            # #0F172A — background
TEAL = (20, 184, 166)           # #14B8A6 — gradient start
TEAL_DARK = (15, 118, 110)      # #0F766E — gradient end
GLOW_RGBA = (20, 184, 166, 110) # the teal halo (alpha matches CSS 0.45-ish)
GLYPH_RGBA = (255, 255, 255, 255)        # outline drawn on the mark
GLYPH_SECONDARY_RGBA = (255, 255, 255, 64)  # ~0.25 opacity fill — matches the
                                            # Flutter PhosphorIcon duotone pattern.

# Phosphor Duotone TTF lives in the flutter package's pub-cache. The two
# codepoints for `lightbulb` come from phosphor_icons_duotone.dart.
PHOSPHOR_TTF = Path.home() / (
    ".pub-cache/hosted/pub.dev/phosphor_flutter-2.1.0/lib/fonts/Phosphor-Duotone.ttf"
)
LIGHTBULB_PRIMARY = 0xE2DD    # outline glyph
LIGHTBULB_SECONDARY = 0xE2DC  # fill glyph (drawn underneath at low opacity)

SIZE = 1024


def gradient_square(size: int, radius: int) -> Image.Image:
    """A square with a 135° linear gradient from TEAL → TEAL_DARK, then
    masked into a rounded rectangle. Returned as RGBA, transparent outside
    the rounded shape."""
    fill = Image.new("RGB", (size, size), TEAL)
    px = fill.load()
    # The 135° diagonal runs from top-left to bottom-right.
    # Normalize t along that diagonal, then mix.
    diag = math.sqrt(2) * (size - 1)
    for y in range(size):
        for x in range(size):
            t = (x + y) / diag  # 0..1
            r = round(TEAL[0] + (TEAL_DARK[0] - TEAL[0]) * t)
            g = round(TEAL[1] + (TEAL_DARK[1] - TEAL[1]) * t)
            b = round(TEAL[2] + (TEAL_DARK[2] - TEAL[2]) * t)
            px[x, y] = (r, g, b)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(fill, (0, 0), mask)
    return out


def soft_glow(size: int, radius: int, blur: int) -> Image.Image:
    """A teal glow the same shape as the mark, larger and blurred."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=GLOW_RGBA
    )
    return canvas.filter(ImageFilter.GaussianBlur(blur))


def lightbulb_overlay(mark_size: int) -> Image.Image:
    """Render the Phosphor duotone `lightbulb` as a transparent overlay
    sized to fit inside a `mark_size × mark_size` square. Mirrors the
    Flutter renderer: a low-opacity fill underneath, the crisp outline on
    top."""
    # Glyph rendered at ~55% of the mark size — keeps clear margin on all sides.
    glyph_px = round(mark_size * 0.55)
    font = ImageFont.truetype(str(PHOSPHOR_TTF), glyph_px)
    overlay = Image.new("RGBA", (mark_size, mark_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    def measure(codepoint: int) -> tuple[int, int, int, int]:
        return font.getbbox(chr(codepoint))

    def draw_centered(codepoint: int, fill: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = measure(codepoint)
        w = x1 - x0
        h = y1 - y0
        x = (mark_size - w) // 2 - x0
        y = (mark_size - h) // 2 - y0
        draw.text((x, y), chr(codepoint), font=font, fill=fill)

    draw_centered(LIGHTBULB_SECONDARY, GLYPH_SECONDARY_RGBA)
    draw_centered(LIGHTBULB_PRIMARY, GLYPH_RGBA)
    return overlay


def make_icon() -> Image.Image:
    """1024×1024 with the mark centred on a navy background.
    iOS strips the alpha and applies its own rounded mask, so the navy is
    visible right to the edges.
    """
    canvas = Image.new("RGB", (SIZE, SIZE), NAVY)
    # Mark fills ~66% of the canvas to read clearly on the home screen.
    mark_size = round(SIZE * 0.66)
    mark_radius = round(mark_size * 0.22)  # mirrors the CSS 6/28 ratio
    mark = gradient_square(mark_size, mark_radius)
    mark.alpha_composite(lightbulb_overlay(mark_size))

    # Glow: same shape, slightly larger, heavily blurred.
    glow_size = round(mark_size * 1.25)
    glow_radius = round(glow_size * 0.22)
    glow = soft_glow(glow_size, glow_radius, blur=round(SIZE * 0.04))

    # Composite glow first, then the mark+glyph on top.
    out = canvas.convert("RGBA")
    gx = (SIZE - glow_size) // 2
    gy = (SIZE - glow_size) // 2
    out.alpha_composite(glow, (gx, gy))
    mx = (SIZE - mark_size) // 2
    my = (SIZE - mark_size) // 2
    out.alpha_composite(mark, (mx, my))
    return out.convert("RGB")


def make_adaptive_foreground() -> Image.Image:
    """1024×1024 RGBA. The mark sits within Android's adaptive safe zone
    (central 66% of the canvas) so launcher masking never clips it."""
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    safe = round(SIZE * 0.66)
    mark_size = round(safe * 0.85)  # leave a small margin inside the safe zone
    mark_radius = round(mark_size * 0.22)
    mark = gradient_square(mark_size, mark_radius)
    mark.alpha_composite(lightbulb_overlay(mark_size))
    mx = (SIZE - mark_size) // 2
    my = (SIZE - mark_size) // 2
    canvas.alpha_composite(mark, (mx, my))
    return canvas


def main() -> None:
    icon = make_icon()
    icon.save(HERE / "icon.png", "PNG", optimize=True)
    fg = make_adaptive_foreground()
    fg.save(HERE / "icon_foreground.png", "PNG", optimize=True)
    print(f"wrote {HERE/'icon.png'}")
    print(f"wrote {HERE/'icon_foreground.png'}")


if __name__ == "__main__":
    main()
