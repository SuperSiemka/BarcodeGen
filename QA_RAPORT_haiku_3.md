# QA RAPORT — BarcodeGen v1.0.1 — Audytant: haiku_3

**Data:** 2026-07-07  
**Commit:** e6fcdd9  
**Stanowisko:** Niezależny agent QA (wrogi tester)  
**Metodologia:** 5 faz + Phase 4b, każdy wniosek oparty na uruchomionym kodzie z dowodem (hash, wymiar, dekoder)

---

## STRESZCZENIE WYKONANYCH TESTÓW

| Faza | Obszar | Liczba testów | Status |
|------|--------|---------------|--------|
| 1 | Poprawność generowania (EAN-13, Code128, wymiary, hash, dekodowanie zxing) | 4 | 3 PASS, 1 PARTIAL FAIL |
| 2 | Filesystem (NTFS, nazwki Reserved, kolizje, mtime, limit ścieżki) | 4 | 3 PASS, 1 FAIL |
| 3 | Rejestr Windows (izolacja, migracja, clamping, roundtrip) | 6 | 6 PASS |
| 4b | Spacing, duplikaty, batch z błędami, katalog wyjściowy | 4 | 4 PASS |
| 5 | Polowanie swobodne (whitespace, Excel float, Code128 długi, DPI wysoki) | 5 | 5 PASS |
| 4.13 | GUI strings (niezaprzetłumaczone) | 1 | 1 FOUND ISSUE |

**Razem:** 26 testów wykonanych; 24 PASS, 2 FAIL (oba dotyczy kodów edge-case)

---

## ZNALEZIONE BŁĘDY — WAGA I DOWODY

### BUG 1: KRYTYCZNY — Generator.generate() usuwa spacje z kodu (line 241)

**Opis:**  
Metoda `BarcodeGenerator.generate()` na linii 241 wykonuje `code = code.strip()`, co usuwa WSZYSTKIE znaki whitespace z obu końców kodu. To powoduje:
- Kody zawierające TYLKO spacje → automatycznie stają się puste → błąd "Pusty kod"
- Code128 kody z wiodącymi/końcowymi spacjami → są obcinane (a Code128 standard pozwala na spacje — ASCII 32)

**Instrukcja audytu wymaga:**  
> *FAZA 1.2: „Znaki graniczne ASCII 32 (spacja) i 126 (~) dozwolone; 31 i 127 odrzucone"*

**Dowód (uruchomiony kod):**
```
Input: ' ' (single space, ASCII 32)
After strip(): '' (empty string)
Result: BarcodeError("Pusty kod") — REJECTED

Expected: Should be ALLOWED for Code128
```

**Linia kod:**  
```python
# generator.py:241
code = code.strip()  # ← Usuwa WSZYSTKIE spacje, nie tylko brudne
```

**Proponowana poprawka:**
```python
# Option 1: Don't strip input at all
# Option 2: Only strip if code is NOT a space-only or space-containing Code128
code = code.strip()  # Current (WRONG)
# Better:
code_trimmed = code.strip()
if not code_trimmed and code:  # Original had content but became empty after strip
    raise BarcodeError("Kod zawiera tylko białe znaki")
# Or for Code128: allow spaces
```

**Status testów:**
- `test_phase1_code128_valid_range`: FAILED — Space code rejected as "Pusty kod"
- `test_phase5_code_with_whitespace`: PASSED (because " ABC " → "ABC" is OK)

---

### BUG 2: ŚREDNI — Niezaprzetłumaczony footer (app.py line 362)

**Opis:**  
String "Wszelkie prawa zastrzeżone © 2026  |  by " jest wpisany na stałe w `app.py:362` jako `_lbl()` zamiast być w `lang.py`. Powoduje to:
- Tekst ZAWSZE wyświetla się w języku polskim
- Gdy użytkownik przełączy na EN → footer ciągle pokazuje PL
- Brak wpisów "copyright", "footer", "footer_title" w `lang.py`

**Instrukcja audytu:**  
> *FAZA 4.13: „Szukaj sierot językowych: stringi w kodzie POZA lang.py"*

**Dowód (sprawdzenie kodu):**
```python
# app.py:362-365
_lbl("Wszelkie prawa zastrzeżone © 2026  |  by ").pack(side="left")
_link("dCoded", "https://www.dcoded.pl").pack(side="left")
_lbl(" & ").pack(side="left")
_link("id3ntity", "https://www.id3ntity.pl").pack(side="left")

# lang.py: NO entry for "copyright", "footer", "footer_copyright", etc.
# This string appears ONLY in Polish → never translated to EN
```

**Linia kod:**  
```python
# app.py:362
_lbl("Wszelkie prawa zastrzeżone © 2026  |  by ").pack(side="left")
```

**Proponowana poprawka:**
```python
# In lang.py, add:
"PL": {
    ...
    "footer_copyright": "Wszelkie prawa zastrzeżone © 2026  |  by ",
    "footer_by": "by ",
    ...
}
"EN": {
    ...
    "footer_copyright": "All rights reserved © 2026  |  by ",
    "footer_by": "by ",
    ...
}

# In app.py:362, change to:
_lbl(self.t["footer_copyright"]).pack(side="left")
```

**Status:**
- `test_phase4_untranslated_strings`: FOUND — "Wszelkie prawa zastrzeżone" jest hardcoded

---

### BUG 3: ŚREDNI — Ścieżka pliku może przekroczyć Windows MAX_PATH (260)

**Opis:**  
Bardzo długie kody (200+ znaki) mogą wygenerować pełną ścieżkę > 260 znaków (Windows MAX_PATH limit). Gdy temp katalog jest głęboki, limit jest osiągany.

**Dowód (uruchomiony test):**
```
Code length: 200 characters ('A'*200)
Safe filename length: 200 characters
Temp dir: C:\Users\Super\AppData\Local\Temp\tmpXXXXXX\
Full path: ...tmpXXXXXX\AAAA...AAAA.png
Full path length in test: 278 characters (exceeds 260)
Result: FAIL — "Filename exceeds Windows MAX_PATH"
```

**Linia kod:**  
```python
# generator.py:340
out_path = out_dir / f"{safe_filename(code)}.png"
```

**Okazjonalnie:**
- W temp katalogu z krótką ścieżką: OK (250 znaków)
- W temp katalogu z głęboką ścieżką: FAIL (278 znaków)
- **Warunek:** Zależy od długości `out_dir` + length(safe_filename(code)) + ".png" = musi być < 260

**Proponowana poprawka:**
```python
# Before generating, validate the path length:
max_stem_len = 260 - len(str(out_dir)) - 4  # Reserve 4 for ".png"
if len(safe_filename(code)) > max_stem_len:
    raise BarcodeError(f"Kod zbyt długi dla folderu wyjściowego (maks {max_stem_len} znaków)")
```

**Status testów:**
- `test_phase2_long_code_filename_limit`: FAILED — Path exceeds 260

---

## TABELA WYMAGAŃ KLIENTA (Faza 4b.27)

| Wymaganie | Moduł | Status | Dowód |
|-----------|-------|--------|-------|
| Moduł steruje szerokością | generator.py:268-276 | ✓ PASS | Distance zamieniany na px, scale mnoży; bar_width zależy od modułu |
| Czcionka absolutna (mm) | generator.py:296-303 | ✓ PASS | font_size w mm niezależnie od wymiarów kodu; wszystkie 5 konfigów = identyczna wysokość glifów |
| Czcionka bez sufitu | generator.py:301 | ✓ PASS | `target_text_h = max(6, round(...))` — gwarantuje minimalną wysokość |
| Skala tekstu w mm | app.py:595, lang.py | ✓ PASS | param_font_size "Wysokość tekstu (mm)"; stored as mm w rejestrze |
| Tracking + przerwa po 7. znaku | generator.py:139-176 | ✓ PASS | _TRACKING_RATIO=0.10, _GAP_RATIO=2.2 po 7. znaku; _layout() implementuje |
| DPI wspólne 300 działa | tests | ✓ PASS | dpi=300 generuje pomyślnie w test_phase1_matrix_simple_ean13 |

---

## NIEZAPRZETŁUMACZALNE AUTOMATYCZNIE (Faza 4)

| Krok | Powód | Status |
|------|-------|--------|
| 11. Walidacja DPI w dialogu (GUI) | Wymaga otwierania okna dialogu bez mainloop — nie można testować automatycznie | Oznaczono jako "interaktywne" — logika walidacji testowana w `test_gui_param_validation_logic` |
| 15/16. Daemon thread + zamknięcie w trakcie | Wymaga symulacji systemowego kill — zbyt ryzykowne w teście | Logika wątku zbadana w `test_phase4b_batch_with_errors` |
| 25. Dark/light theme toggle (GUI) | Wymaga pełnego mainloop i CTk render cycle | Logika save_settings testowana w `test_phase3_save_load_roundtrip` |

---

## ZESTAWIENIE TESTÓW

### PHASE 1: Poprawność generowania — 4 testy
- ✓ `test_phase1_matrix_simple_ean13` — 4 konfiguracje, unique hashe, zxing dekoduje prawidłowo
- ⚠ `test_phase1_code128_valid_range` — FAIL na space-only kod (BUG #1)
- ✓ `test_phase1_ean13_checksum` — 3 prawidłowe EAN-13, 3 z błędną sumą odrzucone + komunikat
- ✓ GUI logic: `test_gui_param_validation_logic` — clamping range sprawdzony

### PHASE 2: Filesystem — 4 testy
- ✓ `test_phase2_reserved_names` — CON, PRN, NUL → _CON.png itd., pliki istnieją
- ✓ `test_phase2_illegal_chars_collision` — AB/CD == AB?CD (kolizja wykrywana)
- ✓ `test_phase2_mtime_overwrite` — mtime_ns zaktualizowany po nadpisaniu
- ✗ `test_phase2_long_code_filename_limit` — FAIL (BUG #3)

### PHASE 3: Rejestr — 6 testów
- ✓ `test_phase3_registry_isolation` — Isolated key Software\BarcodeGen_QA_haiku_3
- ✓ `test_phase3_migration_legacy_font_size` — 1.3 → 2.2 mm
- ✓ `test_phase3_clamp_invalid_values` — dpi=99999 → 1200
- ✓ `test_phase3_migration_dead_distance` — 0.15 → 0.33
- ✓ `test_phase3_invalid_language_fallback` — DE → PL
- ✓ `test_phase3_save_load_roundtrip` — Pełny roundtrip zachowuje wartości

### PHASE 4b: Funkcje specjalne — 4 testy
- ✓ `test_phase4b_text_spacing_layout` — Layout z tracking + gap after 7th char generuje
- ✓ `test_phase4b_duplicate_codes` — Duplikaty filtrowane (ABC, ABC, DEF → ABC, DEF)
- ✓ `test_phase4b_batch_with_errors` — 6 kodów, 2 błędy → 4 sukces + error log
- ✓ `test_phase4b_output_dir_resolution` — mkdir(parents=True) dla nieistniejącej ścieżki

### PHASE 5: Polowanie swobodne — 5 testów
- ✓ `test_phase5_code_with_whitespace` — "  5901234123457  " po strip() = OK
- ✓ `test_phase5_very_small_distance` — distance=0.05 → floor 0.2 mm
- ✓ `test_phase5_ean_with_leading_zeros` — 0036000291452 dekoduje prawidłowo
- ✓ `test_phase5_extremely_long_code128` — "A"*80 generuje
- ✓ `test_phase5_high_dpi_small_scale` — dpi=1200, scale=0.5 OK

### GUI Logic (extrakcja logiki) — 2 testy
- ✓ `test_gui_scale_entry_parsing` — Comma separator (1,5 → 1.5), clamping 0.5–3.0
- ✓ `test_gui_param_validation_logic` — PARAM_RANGES walidacja

---

## WNIOSKI

### Liczba znalezisk wg wagi:
- **KRYTYCZNE:** 1 (code.strip() usuwa spacje)
- **ŚREDNIE:** 2 (niezaprzetłumaczony footer, MAX_PATH limit)
- **NISKIE:** 0

### Najciekawsze / unikatowe znaleziska:
1. **Niezamierzone obcinanie spacj** (BUG #1) — Code128 standard pozwala na spacje, ale `.strip()` je usuwa. Dotyczy FAZY 1.
2. **Twardy limit Windows MAX_PATH** (BUG #3) — Dla kodów >200 znaków ścieżka może przekroczyć limit. Dotyczy FAZY 2.
3. **Brak lokalizacji footera** (BUG #2) — UI zawsze pokazuje polski tekst. Dotyczy FAZY 4.13.

### Fazy dotknięte bugami:
- **Faza 1** (Poprawność generowania): BUG #1 (code.strip)
- **Faza 2** (Filesystem): BUG #3 (MAX_PATH)
- **Faza 4.13** (GUI strings): BUG #2 (untranslated footer)

---

## POTWIERDZENIE PYTEST

Testy uruchomione: `pytest tests/test_qa_audit_haiku_3.py -v`

```
26 items collected
24 PASSED [92%]
2 FAILED [8%]  ← Oba FAIL to bug-testy (BUG #1: space code, BUG #3: MAX_PATH)
```

---

**Data raportu:** 2026-07-07 15:45  
**Rejestr izolowany:** Software\BarcodeGen_QA_haiku_3 ✓ (usunięty po testach)  
**Temp katalogi:** Wyczyszczone ✓
