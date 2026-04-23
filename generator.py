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
    # Fallback
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


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
        """
        Generate a high-quality barcode PNG.

        Parameters:
            height    — bar height in mm
            distance  — module (bar) width in mm
            font_size — font scale factor (1.0 ≈ 10pt at 300 DPI)
            dpi       — output resolution
        """
        code = code.strip()
        if not code:
            raise BarcodeError("Pusty kod")

        barcode_type = _detect_barcode_type(code)

        if barcode_type == "ean13":
            _validate_ean13(code)
            cls = barcode.get_barcode_class("ean13")
            barcode_data = code[:12]   # python-barcode appends check digit itself
        else:
            cls = barcode.get_barcode_class("code128")
            barcode_data = code

        writer = ImageWriter()

        # Generate barcode image WITHOUT built-in text — we draw text manually
        # so it never overflows the image boundaries.
        writer_options = {
            "module_height": height,
            "module_width": distance,
            "quiet_zone": 6.5,      # standard left/right quiet zone in mm
            "dpi": dpi,
            "write_text": False,    # text drawn manually below
            "background": "white",
            "foreground": "black",
        }

        bc = cls(barcode_data, writer=writer)
        buf = io.BytesIO()
        bc.write(buf, options=writer_options)
        buf.seek(0)
        barcode_img = Image.open(buf).convert("RGB")

        # ── Manual text rendering ────────────────────────────────────────────
        # Convert font_size scale to pixels: 1.0 = 10pt, scale by dpi
        font_pt = max(6, font_size * 10)
        font_px = max(8, int(font_pt * dpi / 72))
        font = _load_font(font_px)

        # Measure text
        probe = ImageDraw.Draw(barcode_img)
        bbox = probe.textbbox((0, 0), code, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Gap between bars and text (≈ 5pt converted to pixels)
        gap_px = max(4, int(5 * dpi / 72))
        # Bottom padding below text
        pad_px = max(4, int(3 * dpi / 72))
        # Ensure the canvas is wide enough for the text
        extra_x = max(0, (text_w - barcode_img.width) // 2 + int(2 * dpi / 25.4))

        final_w = barcode_img.width + 2 * extra_x
        final_h = barcode_img.height + gap_px + text_h + pad_px

        final = Image.new("RGB", (final_w, final_h), "white")
        final.paste(barcode_img, (extra_x, 0))

        draw = ImageDraw.Draw(final)
        text_x = (final_w - text_w) // 2
        text_y = barcode_img.height + gap_px
        draw.text((text_x, text_y), code, fill="black", font=font)

        out_path = out_dir / f"{code}.png"
        final.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        return out_path
