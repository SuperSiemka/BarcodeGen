"""
Barcode generation logic — EAN-13 and Code128
"""

import io
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image


class BarcodeError(Exception):
    """Raised when a barcode cannot be generated (invalid data, checksum, etc.)"""


def _ean13_checksum(digits: str) -> int:
    """Calculate EAN-13 check digit from first 12 digits."""
    total = 0
    for i, ch in enumerate(digits[:12]):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def _detect_barcode_type(code: str) -> str:
    """Return 'ean13' or 'code128' based on code content."""
    if code.isdigit() and len(code) == 13:
        return "ean13"
    return "code128"


def _validate_ean13(code: str) -> None:
    """Raise BarcodeError if EAN-13 checksum is wrong."""
    if not code.isdigit() or len(code) != 13:
        raise BarcodeError(f"EAN-13 must be exactly 13 digits, got: '{code}'")
    expected = _ean13_checksum(code)
    actual = int(code[-1])
    if expected != actual:
        raise BarcodeError(
            f"EAN-13 checksum failed for '{code}': "
            f"expected check digit {expected}, got {actual}"
        )


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
        Generate a barcode PNG for *code* and save it to out_dir/<code>.png.
        Returns the path of the created file.
        Raises BarcodeError on invalid input.
        """
        code = code.strip()
        if not code:
            raise BarcodeError("Empty code")

        barcode_type = _detect_barcode_type(code)

        if barcode_type == "ean13":
            _validate_ean13(code)
            cls = barcode.get_barcode_class("ean13")
            # python-barcode expects 12 digits for EAN-13 (adds check digit internally)
            # but since we already validated the full 13-digit code, strip last digit
            barcode_data = code[:12]
        else:
            cls = barcode.get_barcode_class("code128")
            barcode_data = code

        writer = ImageWriter()

        writer_options = {
            "module_height": height,
            "quiet_zone": distance * 10,   # python-barcode uses mm, quiet_zone is in mm
            "font_size": int(font_size * 10),
            "text_distance": distance * 10,
            "dpi": dpi,
            "write_text": True,
        }

        bc = cls(barcode_data, writer=writer)

        buf = io.BytesIO()
        bc.write(buf, options=writer_options)
        buf.seek(0)

        img = Image.open(buf)

        out_path = out_dir / f"{code}.png"
        img.save(str(out_path), format="PNG", dpi=(dpi, dpi))

        return out_path
