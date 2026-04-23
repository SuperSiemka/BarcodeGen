"""
Barcode generation logic — EAN-13 and Code128
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


def _load_font(size_px: int) -> ImageFont.FreeTypeFont:
    """Load a system TrueType font, fall back to PIL built-in."""
    candidates: list[str] = []
    if platform.system() == "Windows":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        candidates = [
            os.path.join(fonts_dir, "arial.ttf"),
            os.path.join(fonts_dir, "calibri.ttf"),
            os.path.join(fonts_dir, "verdana.ttf"),
            os.path.join(fonts_dir, "cour.ttf"),
        ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size_px)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def _generate_ean13(
    code: str,
    out_path: Path,
    height: float,
    distance: float,
    font_size: float,
    dpi: int,
) -> None:
    """
    EAN-13: let python-barcode render bars AND text — it knows the standard
    positioning (first digit to the left, guard bars extended, digit groups).
    We post-process to ensure the left digit is never clipped.
    """
    cls = barcode.get_barcode_class("ean13")
    bc = cls(code[:12], writer=ImageWriter())  # library appends check digit

    font_pt = max(6, font_size * 10)

    writer_options = {
        "module_height": height,
        "module_width": distance,
        # quiet_zone must be wide enough to show the first digit that EAN-13
        # places to the LEFT of the left guard bar.
        # At 300 DPI, one character ≈ font_pt * 300/72 * 0.65 px.
        # 10 mm @ 300 DPI = 118 px — comfortably wider than any digit.
        "quiet_zone": 10.0,
        "font_size": int(font_pt),
        "text_distance": 5.0,
        "dpi": dpi,
        "write_text": True,   # use built-in EAN-13 text (groups + dots)
        "background": "white",
        "foreground": "black",
    }

    buf = io.BytesIO()
    bc.write(buf, options=writer_options)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    # Guard: add left padding if the first digit is somehow at the very edge
    left_margin_px = int(10 * dpi / 25.4)  # 10 mm in pixels
    if img.width < left_margin_px * 2:
        # extremely narrow image — add padding
        padded = Image.new("RGB", (img.width + left_margin_px, img.height), "white")
        padded.paste(img, (left_margin_px, 0))
        img = padded

    img.save(str(out_path), format="PNG", dpi=(dpi, dpi))


def _generate_code128(
    code: str,
    out_path: Path,
    height: float,
    distance: float,
    font_size: float,
    dpi: int,
) -> None:
    """
    Code128: generate bars without text, then draw centered text manually
    so it never overflows the image boundaries.
    """
    cls = barcode.get_barcode_class("code128")
    bc = cls(code, writer=ImageWriter())

    writer_options = {
        "module_height": height,
        "module_width": distance,
        "quiet_zone": 6.5,
        "dpi": dpi,
        "write_text": False,
        "background": "white",
        "foreground": "black",
    }

    buf = io.BytesIO()
    bc.write(buf, options=writer_options)
    buf.seek(0)
    barcode_img = Image.open(buf).convert("RGB")

    # ── Manual text rendering ────────────────────────────────────────────────
    font_pt = max(6, font_size * 10)
    font_px = max(8, int(font_pt * dpi / 72))
    font = _load_font(font_px)

    probe = ImageDraw.Draw(barcode_img)
    bbox = probe.textbbox((0, 0), code, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    gap_px = max(4, int(5 * dpi / 72))
    pad_px = max(4, int(3 * dpi / 72))
    extra_x = max(0, (text_w - barcode_img.width) // 2 + int(4 * dpi / 25.4))

    final_w = barcode_img.width + 2 * extra_x
    final_h = barcode_img.height + gap_px + text_h + pad_px

    final = Image.new("RGB", (final_w, final_h), "white")
    final.paste(barcode_img, (extra_x, 0))

    draw = ImageDraw.Draw(final)
    draw.text(((final_w - text_w) // 2, barcode_img.height + gap_px), code,
              fill="black", font=font)

    final.save(str(out_path), format="PNG", dpi=(dpi, dpi))


class BarcodeGenerator:
    def generate(
        self,
        code: str,
        out_dir: Path,
        height: float = 9.0,
        distance: float = 0.15,
        font_size: float = 1.3,
        dpi: int = 300,
    ) -> Path:
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")

        barcode_type = _detect_barcode_type(code)
        out_path = out_dir / f"{code}.png"

        if barcode_type == "ean13":
            _validate_ean13(code)
            _generate_ean13(code, out_path, height, distance, font_size, dpi)
        else:
            _generate_code128(code, out_path, height, distance, font_size, dpi)

        return out_path
