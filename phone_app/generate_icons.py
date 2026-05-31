"""
generate_icons.py - PWA icin PNG ikon uretici.

Cikti:
  phone_app/icons/icon-192.png            (any purpose - kose yumusatilmis)
  phone_app/icons/icon-512.png            (any purpose)
  phone_app/icons/icon-maskable-192.png   (Android adaptive icon - safe zone)
  phone_app/icons/icon-maskable-512.png   (maskable - tam dolgu)
  phone_app/icons/favicon-32.png          (browser tab)

Calistirma:
  python phone_app/generate_icons.py
"""
from __future__ import annotations
import os
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).parent / "icons"
OUT_DIR.mkdir(exist_ok=True, parents=True)

BG_DARK = (14, 17, 23)
ACCENT_1 = (255, 75, 75)
ACCENT_2 = (255, 140, 66)
ACCENT_3 = (255, 217, 61)
WHITE = (250, 250, 250)


def _gradient(size: int) -> Image.Image:
    """Diagonal gradient (kirmizi -> turuncu -> sari)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            if t < 0.5:
                ratio = t / 0.5
                r = int(ACCENT_1[0] + (ACCENT_2[0] - ACCENT_1[0]) * ratio)
                g = int(ACCENT_1[1] + (ACCENT_2[1] - ACCENT_1[1]) * ratio)
                b = int(ACCENT_1[2] + (ACCENT_2[2] - ACCENT_1[2]) * ratio)
            else:
                ratio = (t - 0.5) / 0.5
                r = int(ACCENT_2[0] + (ACCENT_3[0] - ACCENT_2[0]) * ratio)
                g = int(ACCENT_2[1] + (ACCENT_3[1] - ACCENT_2[1]) * ratio)
                b = int(ACCENT_2[2] + (ACCENT_3[2] - ACCENT_2[2]) * ratio)
            px[x, y] = (r, g, b, 255)
    return img


def _rounded_rect_mask(size: int, radius: int) -> Image.Image:
    """Kose yumusatilmis maske."""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    return mask


def _circle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size, size), fill=255)
    return mask


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/seguibl.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_chart_overlay(img: Image.Image) -> None:
    """Sag alta minimal 'momentum yukari ok' grafigi."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    pad = int(w * 0.18)
    x0 = pad
    y0 = h - pad - int(w * 0.05)
    pts = [
        (x0, y0),
        (x0 + (w - 2 * pad) * 0.20, y0 - (w * 0.02)),
        (x0 + (w - 2 * pad) * 0.40, y0 - (w * 0.06)),
        (x0 + (w - 2 * pad) * 0.60, y0 - (w * 0.10)),
        (x0 + (w - 2 * pad) * 0.80, y0 - (w * 0.16)),
        (x0 + (w - 2 * pad) * 1.00, y0 - (w * 0.24)),
    ]
    line_w = max(3, int(w * 0.025))
    d.line(pts, fill=(255, 255, 255, 220), width=line_w, joint="curve")
    last_x, last_y = pts[-1]
    arrow_size = int(w * 0.07)
    d.polygon(
        [
            (last_x + arrow_size * 0.6, last_y - arrow_size * 0.6),
            (last_x - arrow_size * 0.1, last_y - arrow_size * 0.05),
            (last_x + arrow_size * 0.05, last_y + arrow_size * 0.1),
        ],
        fill=(255, 255, 255, 240),
    )


def _make_icon(size: int, *, maskable: bool = False, circular: bool = False) -> Image.Image:
    """Tek bir ikon uret.

    maskable=True ise tam dolgu (Android adaptive icon safe-zone icin %80 alana ic).
    """
    if maskable:
        canvas = _gradient(size)
        inner_size = int(size * 0.80)
        offset = (size - inner_size) // 2
        bg = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        inner_bg = Image.new("RGBA", (size, size), BG_DARK + (0,))
        circle = _circle_mask(inner_size)
        ic = Image.new("RGBA", (inner_size, inner_size), BG_DARK + (255,))
        bg.paste(canvas, (0, 0))
        bg.paste(ic, (offset, offset), circle)
    else:
        gradient = _gradient(size)
        radius = int(size * 0.22)
        mask = _rounded_rect_mask(size, radius)
        bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        bg.paste(gradient, (0, 0), mask)

    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_chart_overlay(overlay)
    bg.alpha_composite(overlay)

    d = ImageDraw.Draw(bg)
    font_size = int(size * 0.55)
    font = _load_font(font_size)
    text = "Q"
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except Exception:
        tw, th = d.textsize(text, font=font)
    text_x = (size - tw) // 2 - bbox[0] if hasattr(font, "getbbox") else (size - tw) // 2
    text_y = (size - th) // 2 - int(size * 0.12) - (bbox[1] if hasattr(font, "getbbox") else 0)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((text_x + 4, text_y + 4), text, font=font, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(size * 0.015)))
    bg.alpha_composite(shadow)

    d.text((text_x, text_y), text, font=font, fill=BG_DARK)

    return bg


def main() -> int:
    print("PWA ikonlari uretiliyor...")

    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-192.png", 192, True),
        ("icon-maskable-512.png", 512, True),
        ("favicon-32.png", 32, False),
    ]
    for name, size, maskable in targets:
        img = _make_icon(size, maskable=maskable)
        out = OUT_DIR / name
        img.save(out, "PNG", optimize=True)
        print(f"  OK  {out}  ({size}x{size}, maskable={maskable})")

    print(f"\nToplam {len(targets)} ikon: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
