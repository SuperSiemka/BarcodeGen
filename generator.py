"""
Barcode generation logic — EAN-13 and Code128.

Text is always rendered manually so it aligns perfectly with the barcode width.
"""

import io
import os
import platform
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


class BarcodeError(Exception):
    """Raised when a barcode cannot be generated (invalid data, checksum, etc.)"""


# ── EAN-13 checksum ──────────────────────────────────────────────────────────

def _ean13_checksum(digits: str) -> int:
    total = 0
    for i, ch in enumerate(digits[:12]):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def _detect_barcode_type(code: str) -> str:
    if code.isdigit() and len(code) == 13:
        return "ean13"
    return "code128"


def _validate_ean13(code: str) -> None:
    if not code.isdigit() or len(code) != 13:
        raise BarcodeError(f"EAN-13 musi mieć dokładnie 13 cyfr, otrzymano: '{code}'")
    expected = _ean13_checksum(code)
    actual = int(code[-1])
    if expected != actual:
        raise BarcodeError(
            f"Błędna suma kontrolna EAN-13 dla '{code}': "
            f"oczekiwano {expected}, jest {actual}"
        )


# ── Font helpers ─────────────────────────────────────────────────────────────

def _find_font_path() -> str | None:
    """Return path to a usable TrueType font on this system."""
    if platform.system() == "Windows":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in ("arial.ttf", "calibri.ttf", "verdana.ttf", "cour.ttf"):
            path = os.path.join(fonts_dir, name)
            if os.path.isfile(path):
                return path
    return None


def _fit_font_to_width(
    text: str,
    target_w: int,
    font_path: str | None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Binary-search for the largest font size where rendered text_width <= target_w.
    Returns the matching font object.
    """
    probe_img = Image.new("RGB", (1, 1))
    probe_draw = ImageDraw.Draw(probe_img)

    if font_path is None:
        # PIL built-in has no size control — just return default
        return ImageFont.load_default()

    lo, hi = 4, 600
    best_font = ImageFont.truetype(font_path, lo)
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid)
        bb = probe_draw.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= target_w:
            best_font = f
            lo = mid + 1
        else:
            hi = mid - 1
    return best_font


# ── Barcode rendering ─────────────────────────────────────────────────────────

def _render_bars(
    barcode_cls,
    data: str,
    height: float,
    distance: float,
    dpi: int,
) -> Image.Image:
    """Generate bar-only (no text) barcode image."""
    bc = barcode_cls(data, writer=ImageWriter())
    writer_options = {
        "module_height": height,
        "module_width": distance,
        "quiet_zone": 6.5,      # standard quiet zone in mm
        "dpi": dpi,
        "write_text": False,    # text added manually
        "background": "white",
        "foreground": "black",
    }
    buf = io.BytesIO()
    bc.write(buf, options=writer_options)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _compose(
    bar_img: Image.Image,
    text: str,
    dpi: int,
    gap_mm: float = 1.5,
    pad_mm: float = 1.0,
) -> Image.Image:
    """
    Compose final image: bars on top, text below.
    Text is scaled to exactly match the bar image width.
    """
    bar_w = bar_img.width
    bar_h = bar_img.height

    font_path = _find_font_path()
    font = _fit_font_to_width(text, bar_w, font_path)

    # Measure final text size
    probe_draw = ImageDraw.Draw(bar_img)
    bb = probe_draw.textbbox((0, 0), text, font=font)
    text_w = bb[2] - bb[0]
    text_h = bb[3] - bb[1]

    gap_px  = max(2, int(gap_mm  * dpi / 25.4))
    pad_px  = max(2, int(pad_mm  * dpi / 25.4))

    final_h = bar_h + gap_px + text_h + pad_px
    final   = Image.new("RGB", (bar_w, final_h), "white")
    final.paste(bar_img, (0, 0))

    draw   = ImageDraw.Draw(final)
    text_x = (bar_w - text_w) // 2
    text_y = bar_h + gap_px
    draw.text((text_x, text_y), text, fill="black", font=font)

    return final


# ── Public generator ──────────────────────────────────────────────────────────

class BarcodeGenerator:
    def generate(
        self,
        code: str,
        out_dir: Path,
        height: float = 9.0,
        distance: float = 0.15,
        font_size: float = 1.3,   # kept for API compat; width-fitting overrides size
        dpi: int = 300,
    ) -> Path:
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")

        barcode_type = _detect_barcode_type(code)

        if barcode_type == "ean13":
            _validate_ean13(code)
            cls      = barcode.get_barcode_class("ean13")
            bar_data = code[:12]   # python-barcode appends check digit
        else:
            cls      = barcode.get_barcode_class("code128")
            bar_data = code

        bar_img  = _render_bars(cls, bar_data, height, distance, dpi)
        final    = _compose(bar_img, code, dpi)
        out_path = out_dir / f"{code}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        return out_path
