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
import math
import os
import time
import platform
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageChops, ImageDraw, ImageFont


class BarcodeError(Exception):
    pass


# Characters illegal in Windows filenames — replaced with "_" when saving.
_ILLEGAL_FS = r'\/:*?"<>|'


def safe_filename(code: str) -> str:
    """Map a code to the on-disk PNG stem, replacing filesystem-illegal chars.

    Shared with the UI so its "file already exists?" check inspects the SAME
    name the generator will actually write (otherwise the overwrite prompt is
    silently skipped for codes containing / \\ : * ? " < > |).
    """
    return "".join("_" if ch in _ILLEGAL_FS else ch for ch in code)


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


def _fit_font_to_height(text: str, target_h: int, font_path: str | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Binary-search for the largest font whose glyph height (bb[3]-bb[1]) <= target_h.

    The font is sized purely from target_h — an ABSOLUTE pixel height derived from
    the text-scale knob and DPI. It does NOT depend on the barcode width or bar
    height, so text size is independent of the code's dimensions (client request).
    """
    if font_path is None:
        return _make_font(None, max(8, target_h))
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lo, hi, best = 4, 2000, _make_font(font_path, 4)
    while lo <= hi:
        mid  = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        bb   = draw.textbbox((0, 0), text, font=font)
        if (bb[3] - bb[1]) <= target_h:
            best = font
            lo   = mid + 1
        else:
            hi   = mid - 1
    return best


# ── Human-readable text layout (tracking + gap after 7th char) ─────────────────

# Extra spacing between every pair of characters, as a fraction of a digit's
# advance width (slight — client asked for "drobne zwiększenie odstępów").
_TRACKING_RATIO = 0.10
# Extra gap inserted after the 7th character, as a multiple of a digit's advance
# width (client: "na szerokość 2 lub 2,5 cyfr"). Applied universally to any code.
_GAP_RATIO = 2.2
_GAP_AFTER = 7

# Absolute human-readable text height, in mm PER UNIT of the text-scale knob.
# Calibrated so the default (font_size=1.3) reproduces the historic EAN-13 look
# (~26 px glyph height @ 300 DPI). Because the target height is derived only from
# this constant, font_size and DPI — never from the barcode's width or bar height —
# the text size is fully independent of the code's dimensions.
_BASE_TEXT_MM = 1.693


def _text_spacing(font) -> tuple[float, float]:
    """Return (tracking_px, gap_px) derived from the font's digit advance width."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    adv  = draw.textlength("0", font=font) or font.size
    return adv * _TRACKING_RATIO, adv * _GAP_RATIO


def _layout(text: str, font, tracking_px: float, gap_px: float) -> tuple[list[tuple[str, float]], float]:
    """Lay out each character with tracking, plus an extra gap after the 7th
    character. Returns ([(char, x_offset), ...], total_advance_width)."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    positions: list[tuple[str, float]] = []
    x = 0.0
    n = len(text)
    for i, ch in enumerate(text):
        positions.append((ch, x))
        x += draw.textlength(ch, font=font)
        if i < n - 1:                       # no trailing spacing after last char
            x += tracking_px
            if i == _GAP_AFTER - 1:
                x += gap_px
    return positions, x


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
        distance:  float = 0.33,   # keep in sync with app.DEFAULT_SETTINGS —
                                   # 0.15 was the legacy dead value (see load_settings migration)
        font_size: float = 1.3,
        dpi:       int   = 300,
        scale:     float = 1.0,
    ) -> Path:
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")
        if dpi <= 0:
            raise BarcodeError(f"DPI musi być dodatnie, otrzymano: {dpi}")

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

        # ── 1. Module size ───────────────────────────────────────────────
        # `distance` is the module width in mm (UI: "Szerokość modułu (mm)").
        # `scale` is the overall size multiplier (UI slider "Rozmiar kodu").
        # Snap the requested width to an integer number of pixels so every bar
        # is edge-aligned (crisp, no sub-pixel blur), then convert back to mm.
        req_module_mm = max(0.05, distance) * scale
        module_px     = max(2, round(req_module_mm * dpi / 25.4))
        module_mm     = module_px * 25.4 / dpi
        if module_mm < 0.2:                                  # scanner/library minimum
            # Round UP to a whole pixel that still satisfies the 0.2 mm floor —
            # rendering a fractional-px module (e.g. 0.2 mm = 2.36 px @300 DPI)
            # would break the integer-px invariant and produce uneven bar widths.
            module_px = max(2, math.ceil(0.2 * dpi / 25.4))
            module_mm = module_px * 25.4 / dpi

        # ── 2. Render bar image (no text) ────────────────────────────────
        # Bar height is `height` (mm) times the overall size multiplier — kept
        # independent of module_px so width and height scale coherently.
        scaled_height = height * scale
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

        # ── 3. Choose font (ABSOLUTE size — independent of code dimensions) ─
        # `font_size` is the text-scale knob (UI: "Skala tekstu"). The glyph
        # height is derived only from font_size × DPI, NOT from the barcode
        # width or bar height — so growing the code (height / module width /
        # overall scale) does NOT change the text, and the knob keeps scaling
        # linearly with no upper cap (client-reported bugs #1a and #1b).
        target_text_h = max(6, round(font_size * _BASE_TEXT_MM * dpi / 25.4))
        font_path     = _find_font_path()
        font          = _fit_font_to_height(code, target_text_h, font_path)

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

        # Because the font is now absolute, the laid-out text can be WIDER than the
        # bars (big text-scale, or a long code). Widen the canvas to fit it so the
        # text is never clipped, then centre both the bars and the text.
        tracking_px, gap_px_layout = _text_spacing(font)
        positions, layout_w = _layout(code, font, tracking_px, gap_px_layout)
        side_pad = max(4, module_px)
        canvas_w = max(canvas_w, int(layout_w) + 2 * side_pad + 8)

        final = Image.new("RGB", (canvas_w, canvas_h), "white")
        final.paste(bar_img, ((canvas_w - bar_img.width) // 2, 0))

        draw = ImageDraw.Draw(final)
        # Centre the laid-out text (tracking + gap-after-7th) on the canvas
        start_x = (canvas_w - layout_w) / 2
        for ch, x_off in positions:
            draw.text((start_x + x_off, draw_y), ch, fill="black", font=font)

        # ── 5. Save — always update mtime even on overwrite ───────────────
        out_path = out_dir / f"{safe_filename(code)}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        # os.utime(path, None) sets atime+mtime to NOW — forces Windows
        # Explorer to show the updated modification timestamp on overwrite
        os.utime(str(out_path), None)
        return out_path
