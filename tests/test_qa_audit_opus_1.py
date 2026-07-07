"""
QA audit (przebieg TAG = opus_1) — niezależny, wrogi test regresyjny BarcodeGen v1.0.1.

Każdy test asertuje AKTUALNE zachowanie uruchomionego kodu (dowód). Testy oznaczone
BUG asertują błędne, ale RZECZYWISTE zachowanie — opisane w QA_RAPORT_opus_1.md.

Izolacja: rejestr wyłącznie w podkluczu Software\\BarcodeGen_QA_opus_1, katalogi w
tempfile.mkdtemp(). Nie dotyka prawdziwego Software\\BarcodeGen ani dist/output.
"""
import math
import os
import tempfile
import time
import winreg
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
import zxingcpp

import app
from generator import (BarcodeGenerator, BarcodeError, safe_filename,
                       _ean13_checksum, _detect_barcode_type)

QA_REG_KEY = r"Software\BarcodeGen_QA_opus_1"


# ── helpers ────────────────────────────────────────────────────────────────────

@pytest.fixture
def gen():
    return BarcodeGenerator()


@pytest.fixture
def outdir():
    return Path(tempfile.mkdtemp(prefix="bcqa_opus1_"))


def _chk(d12: str) -> int:
    """Niezależna implementacja sumy kontrolnej EAN-13 (waga 1,3,1,3,...)."""
    s = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d12))
    return (10 - s % 10) % 10


def _decode(path: Path):
    r = zxingcpp.read_barcodes(Image.open(path))
    return r[0].text if r else None


def _first_bar_row(im: np.ndarray) -> int:
    dr = np.where((im < 128).any(axis=1))[0]
    return int(dr[0])


def _narrowest_bar_px(path: Path) -> int:
    im = np.array(Image.open(path).convert("L"))
    # Ogranicz się do REGIONU PASKÓW (górny blok przed największą przerwą pionową
    # oddzielającą paski od tekstu), potem wybierz najgęstszy wiersz — odporne na
    # paski wysokie na 1 px ORAZ na duży tekst pod kodem.
    dark_rows = np.where((im < 128).any(axis=1))[0]
    diffs = np.diff(dark_rows)
    gaps = np.where(diffs > 1)[0]
    if len(gaps):
        gi = gaps[np.argmax(diffs[gaps])]
        bar_rows = dark_rows[:gi + 1]
    else:
        bar_rows = dark_rows
    dark_counts = (im < 128).sum(axis=1)
    r = int(bar_rows[np.argmax(dark_counts[bar_rows])])
    row = im[r, :] < 128
    runs, inrun, c = [], False, 0
    for v in row:
        if v and not inrun:
            c, inrun = 1, True
        elif v and inrun:
            c += 1
        elif not v and inrun:
            runs.append(c); inrun = False
    if inrun:
        runs.append(c)
    return min(runs)


def _expected_narrow_px(distance, scale, dpi):
    px = max(2, round(max(0.05, distance) * scale * dpi / 25.4))
    if px * 25.4 / dpi < 0.2:
        px = max(2, math.ceil(0.2 * dpi / 25.4))
    return px


def _text_glyph_height(path: Path):
    im = np.array(Image.open(path).convert("L"))
    dark_rows = np.where((im < 128).any(axis=1))[0]
    diffs = np.diff(dark_rows)
    gaps = np.where(diffs > 1)[0]
    if len(gaps) == 0:
        return None
    gi = gaps[np.argmax(diffs[gaps])]
    text_rows = dark_rows[gi + 1:]
    return int(text_rows.max() - text_rows.min() + 1)


def _glyph_gaps(path: Path):
    im = np.array(Image.open(path).convert("L"))
    dark_rows = np.where((im < 128).any(axis=1))[0]
    diffs = np.diff(dark_rows)
    gaps = np.where(diffs > 1)[0]
    gi = gaps[np.argmax(diffs[gaps])]
    text_rows = dark_rows[gi + 1:]
    band = im[text_rows.min():text_rows.max() + 1, :]
    col_dark = (band < 128).any(axis=0)
    runs, inrun = [], False
    start = 0
    for x, v in enumerate(col_dark):
        if v and not inrun:
            start, inrun = x, True
        elif not v and inrun:
            runs.append((start, x - 1)); inrun = False
    if inrun:
        runs.append((start, len(col_dark) - 1))
    gapw = [runs[i + 1][0] - runs[i][1] - 1 for i in range(len(runs) - 1)]
    return runs, gapw


# ── FAZA 1 — poprawność generowania ─────────────────────────────────────────────

def test_ean13_matrix_decodes_and_narrow_bar_formula(gen, outdir):
    """Macierz parametrów: plik powstaje, zxing dekoduje dokładnie kod,
    najwęższy pasek == formuła. Hashe różne między kombinacjami."""
    import hashlib
    code = "5901234123457"
    combos = [
        dict(distance=0.05, scale=0.5, dpi=72,  height=1,   font_size=0.5),
        dict(distance=0.2,  scale=1,   dpi=300, height=9,   font_size=2.2),
        dict(distance=0.33, scale=1,   dpi=300, height=9,   font_size=8),
        dict(distance=1,    scale=1,   dpi=300, height=9,   font_size=15),
        dict(distance=5,    scale=0.5, dpi=72,  height=9,   font_size=2.2),
        dict(distance=0.05, scale=1,   dpi=1200, height=9,  font_size=2.2),
        dict(distance=10,   scale=1,   dpi=300, height=9,   font_size=2.2),
    ]
    hashes = set()
    for c in combos:
        p = gen.generate(code=code, out_dir=outdir, **c)
        assert p.exists() and p.stat().st_size > 0
        assert _decode(p) == code
        assert _narrowest_bar_px(p) == _expected_narrow_px(c["distance"], c["scale"], c["dpi"])
        hashes.add(hashlib.md5(p.read_bytes()).hexdigest())
    # różne parametry -> różne pliki (kwantyzacja nie skleja tych kombinacji)
    assert len(hashes) == len(combos)


def test_code128_decodes(gen, outdir):
    p = gen.generate(code="ABC-123", out_dir=outdir, dpi=300)
    assert _decode(p) == "ABC-123"


def test_font_absolute_identical_px_same_dpi(gen, outdir):
    """font_size=3 przy różnym height/distance/scale, dpi stałe -> identyczna
    wysokość glifów co do piksela."""
    code = "5901234123457"
    configs = [
        dict(height=1, distance=0.2, scale=0.5),
        dict(height=9, distance=0.33, scale=1),
        dict(height=150, distance=1, scale=3),
        dict(height=50, distance=5, scale=2),
        dict(height=9, distance=0.05, scale=1),
    ]
    heights = {_text_glyph_height(gen.generate(code=code, out_dir=outdir, font_size=3, dpi=300, **c))
               for c in configs}
    assert len(heights) == 1
    # kalibracja mm (Arial): ~ font_size*dpi/25.4 ± 2 px
    h = heights.pop()
    assert abs(h - 3 * 300 / 25.4) <= 2


def test_font_scales_with_dpi(gen, outdir):
    code = "5901234123457"
    for dpi in (72, 300, 1200):
        p = gen.generate(code=code, out_dir=outdir, font_size=3, dpi=dpi, height=9)
        assert abs(_text_glyph_height(p) - round(3 * dpi / 25.4)) <= 2


def test_ean13_20_valid_decode(gen, outdir):
    import random
    random.seed(42)
    for _ in range(20):
        base = "".join(random.choice("0123456789") for _ in range(12))
        code = base + str(_chk(base))
        assert _chk(base) == _ean13_checksum(code)  # zgodność z impl. modułu
        p = gen.generate(code=code, out_dir=outdir, dpi=300)
        assert _decode(p) == code


def test_ean13_20_broken_checksum_rejected(gen, outdir):
    import random
    random.seed(7)
    for _ in range(20):
        base = "".join(random.choice("0123456789") for _ in range(12))
        good = _chk(base)
        code = base + str((good + 1) % 10)
        with pytest.raises(BarcodeError) as ei:
            gen.generate(code=code, out_dir=outdir, dpi=300)
        assert f"oczekiwano cyfry kontrolnej {good}" in str(ei.value)


def test_ean13_leading_zeros(gen, outdir):
    for code in ("0000000000000", "0075678164125"):
        p = gen.generate(code=code, out_dir=outdir, dpi=300)
        assert _decode(p) == code


@pytest.mark.parametrize("oc,allowed", [(31, False), (32, True), (126, True), (127, False)])
def test_code128_ascii_boundaries(gen, outdir, oc, allowed):
    code = "A" + chr(oc) + "B"
    if allowed:
        p = gen.generate(code=code, out_dir=outdir, dpi=300)
        assert _decode(p) == code
    else:
        with pytest.raises(BarcodeError):
            gen.generate(code=code, out_dir=outdir, dpi=300)


def test_code128_lengths_and_spaces(gen, outdir):
    for code in ("A", "X" * 80, "AB   CD"):
        p = gen.generate(code=code, out_dir=outdir, dpi=300)
        assert _decode(p) == code
    # same spacje -> strip() czyni kod pustym -> BarcodeError "Pusty kod"
    with pytest.raises(BarcodeError):
        gen.generate(code="     ", out_dir=outdir, dpi=300)


# ── FAZA 2 — pliki i system ─────────────────────────────────────────────────────

@pytest.mark.parametrize("code,stem", [
    ("CON", "_CON"), ("PRN", "_PRN"), ("NUL", "_NUL"),
    ("com5", "_com5"), ("lpt9", "_lpt9"),
])
def test_reserved_names_physically_created(gen, outdir, code, stem):
    assert safe_filename(code) == stem
    p = gen.generate(code=code, out_dir=outdir, dpi=300)
    assert p.name == f"{stem}.png"
    assert p.exists() and p.stat().st_size > 0


def test_filename_collision(gen, outdir):
    assert safe_filename("AB/CD") == safe_filename("AB?CD") == "AB_CD"
    # logika kolizji z _on_generate
    by = {}
    for c in ["AB/CD", "AB?CD", "XY"]:
        by.setdefault(safe_filename(c), []).append(c)
    coll = [v for v in by.values() if len(v) > 1]
    assert coll == [["AB/CD", "AB?CD"]]


def test_overwrite_updates_mtime(gen, outdir):
    p1 = gen.generate(code="TESTMT", out_dir=outdir, dpi=300)
    m1 = os.stat(p1).st_mtime_ns
    time.sleep(0.05)
    p2 = gen.generate(code="TESTMT", out_dir=outdir, dpi=300)
    assert os.stat(p2).st_mtime_ns > m1


def test_long_code_200_chars_no_crash(gen, outdir):
    code = "X" * 200
    p = gen.generate(code=code, out_dir=outdir, dpi=300)
    assert p.exists()


# ── FAZA 3 — ustawienia i rejestr (izolowany podklucz) ──────────────────────────

def _write_reg(**kv):
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, QA_REG_KEY)
    except FileNotFoundError:
        pass
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, QA_REG_KEY)
    for key, v in kv.items():
        winreg.SetValueEx(k, key, 0, winreg.REG_SZ, str(v))
    winreg.CloseKey(k)


@pytest.fixture
def isolated_reg():
    old = app.REG_KEY
    app.REG_KEY = QA_REG_KEY
    yield
    app.REG_KEY = old
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, QA_REG_KEY)
    except FileNotFoundError:
        pass


def test_settings_migrations(isolated_reg):
    _write_reg(language="DE")
    assert app.load_settings()["language"] == "PL"
    _write_reg(theme="neon")
    assert app.load_settings()["theme"] == "dark"
    _write_reg(dpi="99999")
    assert app.load_settings()["dpi"] == 1200
    _write_reg(font_size="12")  # brak font_unit -> 12*1.693=20.316 -> 20.3 -> clamp 15
    assert app.load_settings()["font_size"] == 15.0
    _write_reg(distance="0.15")  # legacy martwy default -> reset do 0.33
    assert app.load_settings()["distance"] == 0.33
    _write_reg(font_size="2.2", font_unit="mm")  # z markerem -> bez migracji
    assert app.load_settings()["font_size"] == 2.2
    _write_reg(scale="5")
    assert app.load_settings()["scale"] == 3.0
    _write_reg(distance="0.02")  # poniżej min 0.05
    assert app.load_settings()["distance"] == 0.05
    _write_reg(height="-5")
    assert app.load_settings()["height"] == 1.0


def test_settings_corrupt_int_falls_back(isolated_reg):
    _write_reg(dpi="300.0")  # int("300.0") rzuca ValueError -> default 300
    assert app.load_settings()["dpi"] == 300


def test_excel_import_logic(outdir):
    import datetime, openpyxl
    xl = outdir / "t.xlsx"
    wb = openpyxl.Workbook(); ws = wb.active
    for r in [123, 45.0, "hello", "=1+2", None,
              datetime.datetime(2024, 1, 2, 3, 4, 5), 5907925017654]:
        ws.append([r])
    wb.save(xl)
    wb2 = openpyxl.load_workbook(xl, read_only=True, data_only=True)
    ws2 = wb2.worksheets[0]
    codes = [str(row[0]).strip()
             for row in ws2.iter_rows(min_row=1, values_only=True)
             if row and row[0] is not None and str(row[0]).strip()]
    wb2.close()
    # None i formuła (data_only=None) pominięte; int/float/data zamienione na str
    assert codes == ["123", "45", "hello", "2024-01-02 03:04:05", "5907925017654"]


def test_excel_float_ean_becomes_code128(gen, outdir):
    """BUG(NISKI): 13-cyfrowy kod z ".0" (float z Excela) trafia jako Code128
    zawierający literalne ".0", NIE jako EAN-13. Cicho, bez ostrzeżenia."""
    code = "5907925017654.0"
    assert _detect_barcode_type(code) == "code128"
    p = gen.generate(code=code, out_dir=outdir, dpi=300)
    assert _decode(p) == "5907925017654.0"  # zawiera ".0", nie jest EAN


# ── FAZA 4 / 4b — logika (bez GUI) ──────────────────────────────────────────────

def test_duplicate_detection_logic():
    codes = ["ABC", "ABC", "XYZ", "ABC", "XYZ"]
    seen, dupes, unique = set(), [], []
    for c in codes:
        if c in seen:
            if c not in dupes:
                dupes.append(c)
        else:
            seen.add(c); unique.append(c)
    assert dupes == ["ABC", "XYZ"]
    assert unique == ["ABC", "XYZ"]


def test_dpi_range_validation_logic():
    lo, hi = app.PARAM_RANGES["dpi"]
    assert not (lo <= 10000 <= hi)   # 10000 odrzucone
    assert lo <= 300 <= hi


@pytest.mark.parametrize("raw,expected", [
    ("1,5", 1.5), ("0.1", 0.5), ("99", 3.0), ("2.55", 2.5),
])
def test_scale_entry_parse(raw, expected):
    v = float(raw.replace(",", "."))
    assert max(0.5, min(3.0, round(v, 1))) == expected


def test_scale_entry_bad_input():
    with pytest.raises(ValueError):
        float("abc".replace(",", "."))


def test_batch_with_errors_in_middle(gen, outdir):
    """10 kodów, 2 błędne sumy -> 8 plików, 2 błędy z powodami."""
    good = []
    for i in range(8):
        base = f"590123412{i:03d}"[:12]
        good.append(base + str(_chk(base)))
    bad = ["5901234123450", "1234567890123"]  # złe sumy
    allc = good[:4] + [bad[0]] + good[4:] + [bad[1]]
    errors, okc = [], 0
    for code in allc:
        try:
            gen.generate(code=code, out_dir=outdir, dpi=300); okc += 1
        except Exception as e:
            errors.append((code, str(e)))
    assert okc == 8
    assert [c for c, _ in errors] == bad
    assert all("suma kontrolna" in m for _, m in errors)


def test_gap_after_7th_char(gen, outdir):
    """Przerwa PO 7. znaku wyraźnie większa niż jednolity tracking (EAN-13)."""
    p = gen.generate(code="5901234123457", out_dir=outdir, font_size=3, dpi=300, height=9)
    runs, gapw = _glyph_gaps(p)
    assert len(runs) == 13
    gap7 = gapw[6]
    others = [g for i, g in enumerate(gapw) if i != 6]
    assert gap7 > 3 * max(others)   # dużo większa (zmierzono ~67 vs ~7)


def test_code128_short_no_gap_artifact(gen, outdir):
    """Code128 <7 znaków: brak sztucznej dużej przerwy (7. znak nie istnieje)."""
    p = gen.generate(code="ABC12", out_dir=outdir, font_size=3, dpi=300, height=9)
    runs, gapw = _glyph_gaps(p)
    assert len(runs) == 5
    assert max(gapw) < 20   # jednolite, żadnej przerwy ~2.2 cyfry


def test_output_dir_resolution(outdir):
    def resolve(base_setting):
        base = base_setting.strip()
        base = Path(base) if base else app.app_dir() / "output"
        base.mkdir(parents=True, exist_ok=True)
        return base
    assert resolve("") == app.app_dir() / "output"
    nested = outdir / "a" / "b" / "c"
    assert resolve(str(nested)).exists()
    bad = "Z:" + chr(92) + "no_such_qa" + chr(92) + "x"
    with pytest.raises(OSError):
        resolve(bad)


# ── FAZA 5 — polowanie swobodne ─────────────────────────────────────────────────

def test_dead_code_count_data_modules_unused():
    """FIXED(N6): martwe _count_data_modules + _PROBE_* usunięte z generator.py."""
    import generator
    src = Path(generator.__file__).read_text(encoding="utf-8")
    assert "_count_data_modules" not in src
    assert "_PROBE_MW_MM" not in src and "_PROBE_QZ_MM" not in src


def test_dead_import_time_unused():
    """FIXED(N6): nieużywany 'import time' usunięty z generator.py."""
    import generator
    src = Path(generator.__file__).read_text(encoding="utf-8")
    assert "import time" not in src


def test_generator_error_messages_polish_only():
    """BUG(NISKI, i18n): komunikaty BarcodeError są tylko po polsku — pojawiają się
    w logu także w trybie EN."""
    import generator
    src = Path(generator.__file__).read_text(encoding="utf-8")
    assert "Błędna suma kontrolna" in src        # brak wariantu EN
    assert "niedozwolone znaki" in src


def test_footer_and_log_tags_are_orphan_strings():
    """PARTIALLY FIXED(N5): the footer copyright string was moved into lang.py
    (now translated PL/EN); app.py references it via self.t. The [OK]/[ERR] log
    tags remain intentional technical constants outside lang.py."""
    app_src  = Path(app.__file__).read_text(encoding="utf-8")
    lang_src = Path(Path(app.__file__).parent / "lang.py").read_text(encoding="utf-8")
    assert "Wszelkie prawa zastrzeżone" not in app_src   # no longer hardcoded in app.py
    assert "footer_copyright" in lang_src and "Wszelkie prawa zastrzeżone" in lang_src
    assert "[ERR]" in app_src                             # tags still literal (by design)


@pytest.mark.parametrize("code", ["AB\tCD", "AB\nCD", "café", "AB\U0001F600"])
def test_control_and_unicode_rejected(gen, outdir, code):
    with pytest.raises(BarcodeError):
        gen.generate(code=code, out_dir=outdir, dpi=300)


def test_bug_max_valid_params_decompression_bomb(gen, outdir):
    """FIXED(Ś1): the max-of-everything combo now raises a clean BarcodeError
    (size guard) instead of a raw PIL DecompressionBombError."""
    lo_d, hi_d = app.PARAM_RANGES["distance"]
    lo_dpi, hi_dpi = app.PARAM_RANGES["dpi"]
    assert hi_d == 10.0 and hi_dpi == 1200
    with pytest.raises(BarcodeError):
        gen.generate(code="5901234123457", out_dir=outdir,
                     distance=hi_d, dpi=hi_dpi, scale=3.0, height=9.0, font_size=2.2)


def test_bug_negative_height_raw_valueerror(gen, outdir):
    """FIXED(N3): negative height now raises a clean BarcodeError instead of a
    raw ValueError from python-barcode."""
    with pytest.raises(BarcodeError):
        gen.generate(code="5901234123457", out_dir=outdir, height=-5, dpi=300)


def test_bug_height_zero_unscannable(gen, outdir):
    """FIXED(N3): height=0 (which produced a blank, undecodable image) now raises
    a clean BarcodeError up front."""
    with pytest.raises(BarcodeError):
        gen.generate(code="5901234123457", out_dir=outdir, height=0, dpi=300)
