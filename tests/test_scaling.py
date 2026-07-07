"""
Regression tests for the two client-reported bugs (FW_ NDA dla Id3ntity):

  BUG #2  "Szerokość modułu (mm)" had no effect — the field mapped to the
          `distance` parameter, which was never used in generate(). Every code
          came out the same width (388 px) regardless of the setting.

  BUG #1  "Skala tekstu" stopped growing above ~2 (fs_ratio was clamped to 2.0)
          and the text size was derived from the code's width/height, so growing
          the code also grew the text.

These tests pin the fixed behaviour so it cannot silently regress.

Run:  python tests/test_scaling.py      (no pytest required)
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generator import BarcodeGenerator, BarcodeError, safe_filename  # noqa: E402

CODE = "5901234123457"          # valid EAN-13
_G   = BarcodeGenerator()
_OUT = Path(tempfile.mkdtemp())


def _render(**kw):
    defaults = dict(height=9.0, distance=0.33, font_size=1.3, dpi=300, scale=1.0)
    defaults.update(kw)
    return _G.generate(CODE, _OUT, **defaults)


def _measure(path):
    """Return (width_px, text_glyph_height_px). Text height is the ink bbox of
    everything below the first full white gap under the bars."""
    im    = np.array(Image.open(path).convert("L"))
    black = im < 128
    rows  = black.sum(axis=1)
    nz    = np.where(rows > 0)[0]
    top   = nz[0]
    gap   = None
    for r in range(top, len(rows) - 2):
        if rows[r] == 0 and rows[r + 1] == 0 and rows[r + 2] == 0:
            gap = r
            break
    text = black[gap:] if gap is not None else black[len(black) // 2:]
    tnz  = np.where(text.sum(axis=1) > 0)[0]
    text_h = int(tnz[-1] - tnz[0] + 1) if len(tnz) else 0
    return im.shape[1], text_h


def _check(name, cond, detail):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name} — {detail}")
    return cond


def test_module_width_changes_barcode_width():
    """BUG #2: larger module width must produce a wider barcode."""
    widths = [_measure(_render(distance=d))[0] for d in (0.20, 0.33, 0.50, 1.00)]
    ok = all(b > a for a, b in zip(widths, widths[1:]))
    return _check("module width scales barcode width", ok,
                  f"widths {widths} must be strictly increasing")


def test_text_scale_keeps_growing():
    """BUG #1a: text scale must grow monotonically with no upper cap."""
    heights = [_measure(_render(font_size=fs))[1] for fs in (1.0, 2.0, 3.0, 4.0, 5.0)]
    ok = all(b > a for a, b in zip(heights, heights[1:]))
    # and 5 must be clearly bigger than 2 (client: "od 3 wzwyż jak 2")
    ok = ok and heights[-1] >= heights[1] * 1.8
    return _check("text scale grows without cap", ok,
                  f"text heights {heights} must strictly increase; 5x >= 1.8*(2x)")


def test_text_independent_of_bar_height():
    """BUG #1b: at fixed font_size, changing bar height must not change text."""
    heights = {ht: _measure(_render(height=ht, font_size=3.0))[1] for ht in (5, 10, 20)}
    ok = len(set(heights.values())) == 1
    return _check("text independent of bar height", ok,
                  f"text heights per bar-height {heights} must all be equal")


def test_text_independent_of_overall_scale():
    """BUG #1b: at fixed font_size, the overall-size slider must not change text."""
    heights = {sc: _measure(_render(scale=sc, font_size=3.0))[1] for sc in (1.0, 2.0, 3.0)}
    ok = len(set(heights.values())) == 1
    return _check("text independent of overall scale", ok,
                  f"text heights per scale {heights} must all be equal")


def test_default_look_unchanged():
    """Regression guard: the default output must match the historic look."""
    w, t = _measure(_render())
    ok = w == 388 and 22 <= t <= 30
    return _check("default look unchanged", ok,
                  f"default width={w}px (want 388), text_h={t}px (want ~26)")


def test_text_never_clipped():
    """Large text scale must widen the canvas, never clip the digits."""
    path = _render(font_size=5.0)
    im   = np.array(Image.open(path).convert("L"))
    # no black pixels touching the left/right/bottom edges (would mean clipping)
    edge_ok = (im[:, 0].min() >= 128 and im[:, -1].min() >= 128 and im[-1, :].min() >= 128)
    return _check("large text not clipped", edge_ok,
                  "no ink on canvas edges at font_size=5")


def test_saved_name_matches_overwrite_check():
    """Codes with filesystem-illegal chars must save under the sanitized name
    that the UI's overwrite check also uses (Code128 special chars)."""
    code = "AB/CD"
    path = BarcodeGenerator().generate(code, _OUT, height=9.0, distance=0.33,
                                       font_size=1.3, dpi=300, scale=1.0)
    ok = (path.name == f"{safe_filename(code)}.png"
          and path.exists()
          and not (_OUT / f"{code}.png").exists())
    return _check("saved name matches sanitized name", ok,
                  f"saved as {path.name!r}, expected {safe_filename(code)+'.png'!r}")


def test_dpi_zero_rejected_cleanly():
    """dpi<=0 must raise a clear BarcodeError, not a raw ZeroDivisionError."""
    try:
        _render(dpi=0)
        return _check("dpi=0 rejected", False, "no error raised")
    except BarcodeError:
        return _check("dpi=0 rejected", True, "BarcodeError raised (not ZeroDivisionError)")
    except Exception as e:
        return _check("dpi=0 rejected", False, f"wrong exception: {type(e).__name__}")


if __name__ == "__main__":
    tests = [
        test_module_width_changes_barcode_width,
        test_text_scale_keeps_growing,
        test_text_independent_of_bar_height,
        test_text_independent_of_overall_scale,
        test_default_look_unchanged,
        test_text_never_clipped,
        test_saved_name_matches_overwrite_check,
        test_dpi_zero_rejected_cleanly,
    ]
    print("Running scaling regression tests...\n")
    results = [t() for t in tests]
    passed  = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
