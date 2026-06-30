"""
Barcode generation logic — EAN-13 and Code128.

Scaling strategy:
  1. scale controls module_px (integer px per bar module, no fractions).
  2. Bar height scales proportionally with module_px.
  3. Font fitted to 70% of canvas width — never overflows horizontally.
  4. Canvas height computed from textbbox y2 (not y2-y0) so vertical
     clipping is impossible regardless of scale or font metrics.
  5. No post-generation PIL scaling → zero blur, crisp bar edges.
"""

import io
import os
import time
import platform
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageChops, ImageDraw, ImageFont


class BarcodeError(Exception):
    pass


# ── EAN-13 validation ─────────────────────────────────────────────────────────

def _ean13_checksum(digits: str) -> int:
    total = 0
    for i, ch in enumerate(digits[:12]):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def _detect_barcode_type(code: str) -> str:
    return "ean13" if (code.isdigit() and len(code) == 13) else "code128"


def _validate_ean13(code: str) -> None:
    if not code.isdigit() or len(code) != 13:
        raise BarcodeError(f"EAN-13 musi mieć dokładnie 13 cyfr, otrzymano: '{code}'")
    expected = _ean13_checksum(code)
    actual   = int(code[-1])
    if expected != actual:
        raise BarcodeError(
            f"Błędna suma kontrolna EAN-13 dla '{code}': "
            f"oczekiwano cyfry kontrolnej {expected}, jest {actual}"
        )


# ── Font helpers ──────────────────────────────────────────────────────────────

def _find_font_path() -> str | None:
    if platform.system() == "Windows":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in ("arialbd.ttf", "arial.ttf", "calibrib.ttf",
                     "calibri.ttf", "verdana.ttf", "cour.ttf"):
            p = os.path.join(fonts_dir, name)
            if os.path.isfile(p):
                return p
    return None


def _make_font(path: str | None, size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        try:
            return ImageFont.truetype(path, size_px)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def _textbbox_full(text: str, font) -> tuple[int, int, int, int]:
    """Return (x0, y0, x2, y2) bounding box of rendered text pixels."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    return draw.textbbox((0, 0), text, font=font)


def _fit_font_to_width(text: str, target_w: int, font_path: str | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Binary-search for largest font size where pixel width <= target_w."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    if font_path is None:
        return _make_font(None, 12)
    lo, hi, best = 4, 800, _make_font(font_path, 4)
    while lo <= hi:
        mid  = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        bb   = draw.textbbox((0, 0), text, font=font)
        if bb[2] - bb[0] <= target_w:
            best = font
            lo   = mid + 1
        else:
            hi   = mid - 1
    return best


# ── Module counting ────────────────────────────────────────────────────────────

_PROBE_MW_MM = 0.5
_PROBE_QZ_MM = 5.0


def _count_data_modules(barcode_cls, data: str, dpi: int) -> int:
    bc  = barcode_cls(data, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf, options={
        "module_width":  _PROBE_MW_MM,
        "module_height": 10,
        "quiet_zone":    _PROBE_QZ_MM,
        "dpi":           dpi,
        "write_text":    False,
        "background":    "white",
        "foreground":    "black",
    })
    buf.seek(0)
    img     = Image.open(buf)
    qz_px   = int(_PROBE_QZ_MM * dpi / 25.4)
    data_px = img.width - 2 * qz_px
    mw_px   = _PROBE_MW_MM * dpi / 25.4
    return max(1, round(data_px / mw_px))


# ── Bar rendering ─────────────────────────────────────────────────────────────

_QUIET_ZONE_MM = 6.5


def _render_bars(barcode_cls, data: str, height_mm: float,
                 module_mm: float, dpi: int) -> Image.Image:
    bc  = barcode_cls(data, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf, options={
        "module_width":  module_mm,
        "module_height": height_mm,
        "quiet_zone":    _QUIET_ZONE_MM,
        "dpi":           dpi,
        "write_text":    False,
        "background":    "white",
        "foreground":    "black",
    })
    buf.seek(0)
    return Image.open(buf).convert("RGB")


# ── Public API ────────────────────────────────────────────────────────────────

class BarcodeGenerator:
    def generate(
        self,
        code:      str,
        out_dir:   Path,
        height:    float = 9.0,
        distance:  float = 0.15,
        font_size: float = 1.3,
        dpi:       int   = 300,
        scale:     float = 1.0,
    ) -> Path:
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")

        barcode_type = _detect_barcode_type(code)
        if barcode_type == "ean13":
            _validate_ean13(code)
            cls      = barcode.get_barcode_class("ean13")
            bar_data = code[:12]
        else:
            cls      = barcode.get_barcode_class("code128")
            bar_data = code
            # Validate Code128 characters before passing to library
            invalid_chars = [ch for ch in bar_data if ord(ch) < 32 or ord(ch) > 126]
            if invalid_chars:
                raise BarcodeError(
                    f"Kod zawiera niedozwolone znaki dla Code128: "
                    f"{', '.join(repr(c) for c in set(invalid_chars))}"
                )

        # ── 1. Module size (integer px → no rounding cascade) ────────────
        ref_module_px = max(2, round(4 * dpi / 300))        # 4px @ 300 DPI
        module_px     = max(2, round(ref_module_px * scale))
        module_mm     = module_px * 25.4 / dpi
        if module_mm < 0.2:                                  # library minimum
            module_mm  = 0.2
            module_px  = max(2, round(module_mm * dpi / 25.4))

        # ── 2. Render bar image (no text) ────────────────────────────────
        scaled_height = height * (module_px / ref_module_px)
        bar_img       = _render_bars(cls, bar_data, scaled_height, module_mm, dpi)

        # Crop horizontal quiet-zone whitespace, keep small side padding
        inverted = ImageChops.invert(bar_img.convert("L"))
        bbox = inverted.getbbox()
        if bbox:
            side_pad = max(4, module_px)
            left  = max(0, bbox[0] - side_pad)
            right = min(bar_img.width, bbox[2] + side_pad)
            bar_img = bar_img.crop((left, 0, right, bar_img.height))

        canvas_w      = bar_img.width

        # ── 3. Choose font ────────────────────────────────────────────────
        # Constraint 1: max 70% of canvas width (horizontal)
        # Constraint 2: max 40% of bar height in pixels (vertical proportionality)
        #   — prevents font being oversized relative to short bars at low scale
        max_text_w = int(canvas_w * 0.70)
        max_text_h = max(8, int(bar_img.height * 0.40))
        font_path  = _find_font_path()
        font       = _fit_font_to_width(code, max_text_w, font_path)

        # Shrink to satisfy both constraints
        while True:
            bb      = _textbbox_full(code, font)
            pixel_w = bb[2] - bb[0]
            pixel_h = bb[3]          # bb[3] = y2 = actual bottom pixel
            if pixel_w <= canvas_w - 8 and pixel_h <= max_text_h:
                break
            max_text_w -= 10
            if max_text_w < 10:
                break
            font = _fit_font_to_width(code, max_text_w, font_path)

        # ── 4. Compose final image ────────────────────────────────────────
        bb    = _textbbox_full(code, font)
        # bb = (x0, y0, x2, y2) — all relative to draw origin (0,0)
        # When we draw text at y=draw_y, actual pixels span [draw_y+y0 .. draw_y+y2]
        # So canvas must be at least: bar_img.height + gap + y2 + bottom_pad
        # gap_px is the VISUAL gap between bar bottom and first text pixel.

        gap_px = max(2, int(0.3 * dpi / 25.4))   # ~0.3 mm visual gap (tight)
        pad_px = max(4, int(1.5 * dpi / 25.4))   # ~1.5 mm bottom safety margin

        # draw_y: position passed to draw.text() such that visual gap = gap_px
        # First pixel of text = draw_y + bb[1], so draw_y = bar_img.height + gap_px - bb[1]
        draw_y   = bar_img.height + gap_px - bb[1]

        # Canvas height: must reach draw_y + bb[2] (last text pixel) + pad
        canvas_h = draw_y + bb[3] + pad_px

        final = Image.new("RGB", (canvas_w, canvas_h), "white")
        final.paste(bar_img, (0, 0))

        draw   = ImageDraw.Draw(final)
        text_x = (canvas_w - (bb[2] - bb[0])) // 2 - bb[0]  # centre pixel content
        draw.text((text_x, draw_y), code, fill="black", font=font)

        # ── 5. Save — always update mtime even on overwrite ───────────────
        safe_name = "".join("_" if ch in r'\/:*?"<>|' else ch for ch in code)
        out_path = out_dir / f"{safe_name}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        # os.utime(path, None) sets atime+mtime to NOW — forces Windows
        # Explorer to show the updated modification timestamp on overwrite
        os.utime(str(out_path), None)
        return out_path
