"""
Barcode generation logic — EAN-13 and Code128.

Quality approach:
  1. Count barcode modules by generating a 1-px-per-module probe image.
  2. Compute module_width so each module is exactly N whole pixels wide.
  3. Generate the real barcode at that size — no post-generation scaling,
     no anti-aliased bar edges, crisp output for print.
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


def _make_font(font_path: str | None, size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size_px)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def _measure_text(text: str, font) -> tuple[int, int]:
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bb    = probe.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


# ── Module counting ────────────────────────────────────────────────────────────

_QUIET_ZONE_MM = 6.5         # real quiet zone used in final image

# Probe module width: large enough to avoid library crashes (≥ 0.2mm),
# gives ~3-6px/module at common DPIs → safe integer arithmetic.
_PROBE_MW_MM   = 0.5
_PROBE_QZ_MM   = _PROBE_MW_MM * 10   # 5.0 mm


def _count_data_modules(barcode_cls, data: str, dpi: int) -> int:
    """
    Render a throwaway image with _PROBE_MW_MM width and _PROBE_QZ_MM quiet
    zone, then compute how many data modules fit in the data area.
    """
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
    img      = Image.open(buf)
    qz_px    = int(_PROBE_QZ_MM * dpi / 25.4)
    data_px  = img.width - 2 * qz_px
    mw_px    = _PROBE_MW_MM * dpi / 25.4     # pixels per module in probe image
    return max(1, round(data_px / mw_px))


# ── Rendering ─────────────────────────────────────────────────────────────────

def _render_bars(barcode_cls, data: str, height: float, module_mm: float, dpi: int) -> Image.Image:
    """Generate bar-only image at the given module_width (no text)."""
    bc  = barcode_cls(data, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf, options={
        "module_width":  module_mm,
        "module_height": height,
        "quiet_zone":    _QUIET_ZONE_MM,
        "dpi":           dpi,
        "write_text":    False,
        "background":    "white",
        "foreground":    "black",
    })
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _compose(
    bar_img:   Image.Image,
    text:      str,
    dpi:       int,
    font_size: float,
    text_w:    int,
    text_h:    int,
    font,
) -> Image.Image:
    """Compose final image: bars + text centred over the data (bar) area."""
    quiet_px = int(_QUIET_ZONE_MM * dpi / 25.4)
    bar_area = max(1, bar_img.width - 2 * quiet_px)

    gap_px = max(2, int(0.5 * dpi / 25.4))     # ~0.5 mm — close but no overlap
    pad_px = max(2, int(1.0 * dpi / 25.4))     # ~1 mm bottom padding

    canvas_w = bar_img.width
    canvas_h = bar_img.height + gap_px + text_h + pad_px
    final    = Image.new("RGB", (canvas_w, canvas_h), "white")
    final.paste(bar_img, (0, 0))

    draw   = ImageDraw.Draw(final)
    # Centre text over bar data area (between the quiet zones)
    text_x = quiet_px + (bar_area - text_w) // 2
    draw.text((text_x, bar_img.height + gap_px), text, fill="black", font=font)
    return final


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

        # ── Step 1: compute text dimensions ──────────────────────────────────
        effective_font_size = max(0.1, font_size * scale)
        font_pt  = max(6.0, effective_font_size * 10)        # e.g. 1.3 * 10 = 13 pt
        font_px  = max(8, int(font_pt * dpi / 72))
        font_path = _find_font_path()
        font     = _make_font(font_path, font_px)
        text_w, text_h = _measure_text(code, font)

        # ── Step 2: count modules, compute integer module_width ───────────────
        n_modules = _count_data_modules(cls, bar_data, dpi)

        # Whole pixels per module → crisp edges, no anti-aliasing on bars
        module_px  = max(1, round(text_w / n_modules))
        module_mm  = module_px * 25.4 / dpi           # back to mm for the writer

        # ── Step 3: render bars at exact size (no scaling) ───────────────────
        bar_img = _render_bars(cls, bar_data, height, module_mm, dpi)

        # ── Step 4: compose ───────────────────────────────────────────────────
        final    = _compose(bar_img, code, dpi, effective_font_size, text_w, text_h, font)
        out_path = out_dir / f"{code}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        return out_path
