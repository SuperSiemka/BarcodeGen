"""
Barcode generation logic — EAN-13 and Code128.

Correct scaling strategy:
  1. scale controls module_px (integer pixels per bar module).
  2. target data width = module_px * n_modules  (exact, no rounding error).
  3. Font is fitted to match target data width exactly.
  4. Actual quiet-zone boundaries are measured from the rendered image
     (pixel scan) so centering is always correct regardless of DPI/library.
  5. No post-generation scaling → zero blur, crisp bar edges at any size.
"""

import io
import os
import platform
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


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


def _measure_text(text: str, font) -> tuple[int, int]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bb   = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def _fit_font_to_width(text: str, target_w: int, font_path: str | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Binary-search for largest font where text_width <= target_w."""
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

_PROBE_MW_MM = 0.5          # safe probe module width (≥ 0.2 mm required)
_PROBE_QZ_MM = 5.0          # known probe quiet zone

def _count_data_modules(barcode_cls, data: str, dpi: int) -> int:
    """Count barcode data modules using a probe render at known module width."""
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


# ── Bar image rendering ────────────────────────────────────────────────────────

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


def _scan_bar_bounds(img: Image.Image) -> tuple[int, int]:
    """
    Scan the middle row of the bar image to find the x-coordinates of the
    first and last black pixel.  Returns (left_x, right_x).
    This gives the actual data area regardless of quiet zone size.
    """
    mid_y  = img.height // 3
    pixels = img.crop((0, mid_y, img.width, mid_y + 1)).convert("L").getdata()
    px     = list(pixels)
    left   = next((i for i, v in enumerate(px)         if v < 128), 0)
    right  = next((i for i, v in enumerate(reversed(px)) if v < 128), img.width - 1)
    right  = img.width - 1 - right
    return left, right


# ── Public API ────────────────────────────────────────────────────────────────

class BarcodeGenerator:
    def generate(
        self,
        code:      str,
        out_dir:   Path,
        height:    float = 9.0,
        distance:  float = 0.15,
        font_size: float = 1.3,   # not used for sizing — kept for API compat
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

        # ── Step 1: integer module_px driven by scale ─────────────────────
        # Reference: 4px/module at 300 DPI = 0.339mm ≈ ISO EAN-13 standard (0.33mm).
        # Scale multiplies this reference.  DPI scales proportionally so physical
        # size stays constant regardless of chosen DPI.
        ref_module_px = max(2, round(4 * dpi / 300))   # 4px@300, 8px@600, etc.
        module_px     = max(2, round(ref_module_px * scale))
        module_mm     = module_px * 25.4 / dpi          # back to mm for renderer
        # python-barcode minimum: ~0.2mm
        if module_mm < 0.2:
            module_mm = 0.2
            module_px = max(2, round(module_mm * dpi / 25.4))

        # ── Step 2: render bars ───────────────────────────────────────────
        n_modules     = _count_data_modules(cls, bar_data, dpi)
        scaled_height = height * (module_px / ref_module_px)
        bar_img       = _render_bars(cls, bar_data, scaled_height, module_mm, dpi)

        # ── Step 3: measure actual bar data bounds from pixels ────────────
        bar_left, bar_right = _scan_bar_bounds(bar_img)
        actual_data_w = bar_right - bar_left + 1   # pixels of actual bars

        # ── Step 4: font constrained to 3/4 of data width ────────────────
        # Hard cap at 75% so number is always visually smaller than barcode
        # and never overflows the canvas regardless of scale.
        max_text_w = int(actual_data_w * 0.75)
        font_path  = _find_font_path()
        font       = _fit_font_to_width(code, max_text_w, font_path)
        text_w, text_h = _measure_text(code, font)

        # Safety clamp — text must never exceed canvas width
        canvas_w = bar_img.width
        if text_w > canvas_w - 4:
            font   = _fit_font_to_width(code, canvas_w - 4, font_path)
            text_w, text_h = _measure_text(code, font)

        # ── Step 5: compose ───────────────────────────────────────────────
        gap_px   = max(2, int(0.4 * dpi / 25.4))   # ~0.4 mm — tight gap
        pad_px   = max(2, int(0.8 * dpi / 25.4))   # ~0.8 mm bottom
        canvas_h = bar_img.height + gap_px + text_h + pad_px
        final    = Image.new("RGB", (canvas_w, canvas_h), "white")
        final.paste(bar_img, (0, 0))

        draw   = ImageDraw.Draw(final)
        text_x = bar_left + (actual_data_w - text_w) // 2
        # Clamp text_x so text never goes outside canvas
        text_x = max(0, min(text_x, canvas_w - text_w))
        draw.text((text_x, bar_img.height + gap_px), code, fill="black", font=font)

        out_path = out_dir / f"{code}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        # Touch mtime explicitly so file manager always shows updated time
        import time
        t = time.time()
        os.utime(str(out_path), (t, t))
        return out_path
