"""
Barcode generation logic — EAN-13 and Code128.

Strategy: generate bars at given module_width, then SCALE the bar image so
that the barcode data area (bars only, excluding quiet zones) matches the
rendered text width. This guarantees perfect visual alignment regardless of
module_width setting.
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
    actual = int(code[-1])
    if expected != actual:
        raise BarcodeError(
            f"Błędna suma kontrolna EAN-13 dla '{code}': "
            f"oczekiwano cyfry kontrolnej {expected}, jest {actual}"
        )


# ── Font helpers ──────────────────────────────────────────────────────────────

def _find_font_path() -> str | None:
    if platform.system() == "Windows":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in ("arial.ttf", "calibri.ttf", "verdana.ttf", "cour.ttf"):
            path = os.path.join(fonts_dir, name)
            if os.path.isfile(path):
                return path
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
    bb = probe.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


# ── Core rendering ────────────────────────────────────────────────────────────

QUIET_ZONE_MM = 6.5   # standard EAN/Code128 quiet zone


def _render_bars(barcode_cls, data: str, height: float, distance: float, dpi: int) -> Image.Image:
    """Generate bar image WITHOUT text."""
    bc = barcode_cls(data, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf, options={
        "module_height": height,
        "module_width":  distance,
        "quiet_zone":    QUIET_ZONE_MM,
        "dpi":           dpi,
        "write_text":    False,
        "background":    "white",
        "foreground":    "black",
    })
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _compose(
    bar_img: Image.Image,
    text: str,
    dpi: int,
    distance: float,
    font_size: float,
) -> Image.Image:
    """
    Scale bar_img so the DATA AREA (bars only, excluding quiet zones) matches
    the rendered text width.  Then compose: bars on top, text centred below.
    """
    # ── 1. Font & text size ───────────────────────────────────────────────
    font_pt  = max(6.0, font_size * 10)          # 1.3 → 13 pt
    font_px  = max(8, int(font_pt * dpi / 72))   # pt → px at given dpi
    font_path = _find_font_path()
    font      = _make_font(font_path, font_px)

    text_w, text_h = _measure_text(text, font)

    # ── 2. Scale bar image so data area == text_w ─────────────────────────
    quiet_px  = int(QUIET_ZONE_MM * dpi / 25.4)          # quiet zone in px
    bar_area  = max(1, bar_img.width - 2 * quiet_px)     # actual bars width

    scale     = text_w / bar_area                         # stretch factor
    new_bar_w = int(bar_img.width  * scale)
    new_bar_h = int(bar_img.height * scale)
    bar_img   = bar_img.resize((new_bar_w, new_bar_h), Image.LANCZOS)

    # ── 3. Compose final image ────────────────────────────────────────────
    canvas_w = bar_img.width                              # text centres within this
    gap_px   = max(4, int(2.0 * dpi / 25.4))             # ~2 mm gap
    pad_px   = max(4, int(1.5 * dpi / 25.4))             # ~1.5 mm bottom padding

    final = Image.new("RGB", (canvas_w, bar_img.height + gap_px + text_h + pad_px), "white")
    final.paste(bar_img, (0, 0))

    draw   = ImageDraw.Draw(final)
    text_x = (canvas_w - text_w) // 2
    draw.text((text_x, bar_img.height + gap_px), text, fill="black", font=font)

    return final


# ── Public API ────────────────────────────────────────────────────────────────

class BarcodeGenerator:
    def generate(
        self,
        code: str,
        out_dir: Path,
        height: float = 9.0,
        distance: float = 0.15,
        font_size: float = 1.3,
        dpi: int = 300,
        scale: float = 1.0,
    ) -> Path:
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")

        barcode_type = _detect_barcode_type(code)

        if barcode_type == "ean13":
            _validate_ean13(code)
            cls      = barcode.get_barcode_class("ean13")
            bar_data = code[:12]   # library appends check digit
        else:
            cls      = barcode.get_barcode_class("code128")
            bar_data = code

        # scale affects font_size → drives overall image size (bars auto-fit to text)
        effective_font_size = max(0.1, font_size * scale)

        bar_img  = _render_bars(cls, bar_data, height, distance, dpi)
        final    = _compose(bar_img, code, dpi, distance, effective_font_size)
        out_path = out_dir / f"{code}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        return out_path
