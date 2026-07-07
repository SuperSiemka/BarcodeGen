# QA RAPORT — przebieg `fable_4` (audyt wrogi, BarcodeGen v1.0.1, commit e6fcdd9)

## Środowisko

| | |
|---|---|
| Data | 2026-07-07 |
| Python | 3.14.3 (win32, Windows 10 Home 19045) |
| Pillow | 12.2.0; dekoder: `zxing-cpp` (`zxingcpp.read_barcodes`) |
| Testy | `tests/test_qa_audit_fable_4.py` — **30 passed in 2.66 s** |
| Rejestr | izolowany podklucz `HKCU\Software\BarcodeGen_QA_fable_4` (patch `app.REG_KEY`), usunięty po testach (`winreg.DeleteKey`, test `test_f5_registry_key_cleanup` potwierdza `FileNotFoundError` przy ponownym otwarciu) |
| Wyjścia | wyłącznie świeże `tempfile.mkdtemp()`; `dist/output` nietknięte |
| Kod aplikacji | `app.py` / `generator.py` / `lang.py` / `tests/test_scaling.py` — **niezmodyfikowane** |

Każdy wniosek poniżej pochodzi z **uruchomionego kodu** (dekodowanie zxing, pomiar pikseli
z obrazu, hash SHA-256, treść wyjątku). Eksploracja pełna: 62 kombinacje × 2 kody
(harness w scratchpadzie); suita finalna utrwala reprezentatywną próbkę + wszystkie bugi.

---

## Wykonane testy + dowody

| # | Test (faza) | Dowód z uruchomienia |
|---|---|---|
| 1 | Macierz parametrów, 62 kombinacje × {EAN `5901234123457`, Code128 `ABC-123`} (F1) | **0 błędów**: każdy plik powstał, zxing dekoduje dokładnie wejście, najwęższy pasek px == `max(2, round(max(0.05,d)·scale·dpi/25.4))` z podłogą 0.2 mm dla WSZYSTKICH kombinacji (m.in. d=0.05, scale=0.5, dpi=1200 → zmierzone 10 px = `ceil(0.2·1200/25.4)`). W suicie: `test_f1_matrix` (24 kombinacje, w tym wszystkie skrajne) |
| 2 | Kolizje hashy | Jedyne identyczne pliki = kombinacje kwantyzujące się do tego samego module_px, np. przy dpi=72, scale=1 dystanse 0.05/0.2/0.33 mm → jeden hash `4232c77d5188ad22` (podłoga 2 px). `test_f1_quantization_collapses_distances_at_72dpi` |
| 3 | Czcionka absolutna (F1.2) | font_size=3 mm, dpi=300, 5 konfiguracji (height 1/9/150, distance 5, scale 3) → wysokość glifów **zmierzona z obrazu = 35 px w każdej** (cel 35.43); dpi 72/300/1200 → 9/35/142 px vs cel 9/35/142 (mm: 3.17/2.96/3.01) |
| 4 | EAN-13 20+20 (F1.3) | 20 losowych z sumą z **niezależnej** implementacji → 20/20 dekoduje; 20 zepsutych → 20/20 `BarcodeError` z tekstem `oczekiwano cyfry kontrolnej {właściwa}` |
| 5 | Code128 granice (F1.4) | `"A B"`, `"A~B"`, `"X"`, 80 znaków, `"A   B"` → wszystkie dekodują 1:1; `\x1f` i `\x7f` → `BarcodeError "niedozwolone znaki"`; same spacje → po strip `"Pusty kod"` |
| 6 | Nazwy zastrzeżone (F2.5) | `CON→_CON.png (2553 B)`, `PRN→_PRN.png`, `NUL→_NUL.png`, `com5→_com5.png`, `lpt9→_lpt9.png` — wszystkie istnieją, rozmiar > 0 |
| 7 | Kolizja nazw (F2.6) | `safe_filename("AB/CD") == safe_filename("AB?CD") == "AB_CD"`; replika logiki `_by_name` z `_on_generate` daje grupę `"AB/CD, AB?CD"` PRZED generowaniem |
| 8 | Nadpisanie mtime (F2.7) | `st_mtime_ns`: 1783448065313661600 → 1783448065370023700 (rośnie; `os.utime` działa) |
| 9 | Kod 200 znaków (F2.8) | ścieżka 383 znaki → plik powstał. **Uwaga**: na tej maszynie `LongPathsEnabled=1` (odczytane z HKLM); na domyślnym Win10 (=0) ta sama generacja by się wysypała — zależne od środowiska |
| 10 | Rejestr (F3.9) | `DE→PL`, `neon→dark`, `99999→1200`, `font_size=12` bez markera → `12·1.693=20.316→20.3→clamp 15.0`, z markerem `mm` → 12.0; `0.15→0.33`; bonus: `scale="-5"→0.5`, `height="1e6"→150.0`, `scale="nan"→3.0` (patrz B-9). Wszystko bez wyjątku |
| 11 | Excel (F3.10) | xlsx: int→`"123"`, float `5907925017654.0`→**`"5907925017654"`** (openpyxl oddaje int dla całkowitego floata — główna ścieżka importu jest bezpieczna), tekst, formuła bez cache→None→pominięta, pusta→pominięta, data→`"2026-01-05 00:00:00"`, `"   "`→pominięta, 500 wierszy → razem 504. String `"5907925017654.0"` podany wprost → patrz B-6 |
| 12 | Walidacja ustawień (F4.11) | replika `_save`: `not (72<=10000<=1200)` → odrzucone; dpi=0, distance=11, height=NaN też odrzucone (NaN: porównania False → ValueError) |
| 13 | Duplikaty kodów (F4b.20) | `["X","X","X","Y"]` → `dupes=["X"]`, `unique=["X","Y"]` |
| 14 | Partia z błędami (F4b.21) | replika pętli `worker()`: 10 kodów (2 złe sumy w środku) → **8 plików PNG**, 2 błędy, oba z `oczekiwano cyfry kontrolnej`, kolejność zachowana |
| 15 | Katalog wyjściowy (F4b.22) | pusty → `app_dir()/output` = katalog obok `app.py` (frozen: obok .exe); nieistniejący zagnieżdżony → `mkdir(parents=True)` tworzy; PLIK w miejscu katalogu → `FileExistsError` (WinError 183), zły dysk `Q:\` → `FileNotFoundError` (WinError 3) — oba to `OSError`, łapane w `_on_generate` |
| 16 | Suwak/entry skali (F4b.24) | `"1,5"→1.5`, `"abc"→przywrócenie`, `"0.1"→0.5`, `"99"→3.0`, `"nan"→3.0`, `"inf"→3.0`, `"1e1"→3.0` |
| 17 | Odstępy tekstu (F4b.19) | EAN-13, pomiar kolumn glifów: 13 glifów, przerwy px = `[5,7,9,11,7,6,`**`67`**`,12,6,6,6,5]` — po 7. znaku 67 px (>3× max reszty), tracking w jednym paśmie; Code128 `"ABC"` (brak 7. znaku): 3 glify, przerwy `[6,7]` — układ nie psuje się; `"ABCDEFGH12"`: przerwa 66 px po 7. znaku (patrz B-10) |
| 18 | Strefa ciszy | pomiar: lewy margines **4 px = 1.0 moduł** przy d=0.33/dpi=300 (patrz B-5) |
| 19 | Zera wiodące EAN | `0000000000000` i `0001234567895` → zxing dekoduje pełne 13 cyfr EAN-13 (nie degraduje do UPC-A) |
| 20 | Stress max parametrów | d=10, scale=3, dpi=1200, height=150 (wszystko W ZAKRESACH) → **118 s CPU**, potem `DecompressionBombError: Image size (2887680066 pixels) exceeds limit of 178956970` (patrz B-1) |

---

## Znalezione błędy

### KRYTYCZNY

**B-1. Wartości w dozwolonych zakresach generują ~2.9-gigapikselowy obraz: ~2 min zawieszenia na kod, potem krach PIL.**
Komentarz nad `PARAM_RANGES` (app.py:40-41) twierdzi, że zakresy zapobiegają „multi-gigapixel
image that hangs or crashes". Fałsz: `distance=10 × scale=3 × dpi=1200 × height=150` —
każda wartość legalna — daje moduł 1417 px, obraz pasków 2 887 680 066 px.
**Dowód (uruchomienie):** po 118 s `DecompressionBombError: Image size (2887680066 pixels)
exceeds limit of 178956970 pixels` (rzucony w `_render_bars` → `Image.open`). W aplikacji:
brak przycisku anulowania, GUI czeka ~2 min NA KAŻDY kod partii, po czym `[ERR]` z kryptycznym
angielskim komunikatem o „decompression bomb DOS attack". Test: `test_f5_BUG_param_ranges_allow_gigapixel_image`
(asercja analityczna width×height > 2×`Image.MAX_IMAGE_PIXELS`; przebieg 118 s udokumentowany powyżej).
**Poprawka:** w `_open_settings._save` i/lub na początku `generate()` walidować ILOCZYN:
`module_px·113·height_px ≤ limit` (np. 100 MPx) i odrzucać z czytelnym komunikatem; ewentualnie
obniżyć sufit `distance·scale` przy dpi>600.

### ŚREDNI

**B-2. Nazwy urządzeń z rozszerzeniem (`con.x`, `nul.x`, `aux.data`, `com1.v2`) nie są sanityzowane — zapis wybucha surowymi wyjątkami.**
`safe_filename` chroni tylko DOKŁADNE nazwy (`stem.upper() in _WIN_RESERVED`), a Windows
rezerwuje też nazwy, w których człon przed pierwszą kropką to urządzenie (`con.x.png` → urządzenie CON).
**Dowód:** `con.x` → `UnsupportedOperation: File or stream is not seekable` (PIL pisze do konsoli!),
`nul.x` → `OSError [WinError 1] Niepoprawna funkcja`, `aux.data`/`com1.v2` → `FileNotFoundError`.
Żaden plik nie powstaje; użytkownik dostaje `[ERR]` z bezsensownym komunikatem. Test:
`test_f2_BUG_device_name_with_extension_crashes`.
**Poprawka:** w `safe_filename` sprawdzać `stem.split(".")[0].upper() in _WIN_RESERVED` (oraz nazwę z doklejonym `.png`).

**B-3. Unicode-owa „cyfra" `²` przecieka jako goły `ValueError` zamiast `BarcodeError`.**
`"590123412345²".isdigit()` → True, len 13 → ścieżka EAN-13; `int('²')` w
`_validate_ean13` (generator.py:74) rzuca `ValueError: invalid literal for int() with base 10: '²'`.
**Dowód:** uruchomienie — wyjątek typu `ValueError`, nie `BarcodeError`. Kontrakt API generatora
złamany (GUI ratuje szerokie `except Exception`, ale log pokazuje surowy angielski komunikat).
Test: `test_f5_BUG_superscript_digit_leaks_valueerror`.
**Poprawka:** w `_detect_barcode_type`/`_validate_ean13` wymagać ASCII: `code.isascii() and code.isdigit()`.

**B-4. Cyfry arabsko-indyjskie AKCEPTOWANE jako EAN-13 — zawartość kodu ≠ wpisany string.**
`"٥٩٠١٢٣٤١٢٣٤٥٧"` przechodzi `isdigit()` + `int()` (suma kontrolna liczy się poprawnie!),
python-barcode renderuje kreski, a pod nimi rysowane są glify arabskie.
**Dowód:** plik `٥٩٠١٢٣٤١٢٣٤٥٧.png` powstaje, zxing dekoduje **`5901234123457`** — czyli co innego
niż wpisany kod; aplikacja zalogowałaby `[OK]`. Test: `test_f5_BUG_arabic_indic_digits_content_mismatch`.
**Poprawka:** jak w B-3 (`isascii()`), wtedy kod trafia do Code128 i jest jawnie odrzucany jako znaki >126.

**B-5. Strefa ciszy (quiet zone) przycięta do ~1 modułu — norma EAN-13 wymaga ≥11 modułów z lewej.**
Generator renderuje 6.5 mm quiet zone, po czym kadruje do `side_pad = max(4, module_px)`.
**Dowód (pomiar z obrazu):** przy d=0.33 mm/dpi=300 lewy margines = 4 px = **1.0 moduł** (spec: 11).
zxing dekoduje czysty plik cyfrowy, ale wydruk „na styk" (naklejka przycięta po krawędzi obrazka)
może nie być skanowalny czytnikami liniowymi. Test: `test_f5_BUG_quiet_zone_cropped_to_one_module`.
**Poprawka:** `side_pad = max(11 * module_px, …)` dla EAN (10 modułów dla Code128), lub opcja w ustawieniach.

**B-6. 13-cyfrowy EAN z artefaktem `.0` („5907925017654.0") jest po cichu generowany jako Code128.**
Baza `5907925017654` to POPRAWNY EAN-13 (niezależna suma = 4), ale z `.0` → `_detect_barcode_type`
→ code128, zero ostrzeżenia.
**Dowód:** plik `5907925017654.0.png` powstaje, zxing: `('5907925017654.0', 'Code 128')`.
Główna ścieżka importu jest częściowo bezpieczna — openpyxl oddaje całkowite floaty jako int
(dowód: komórka `=5907925017654.0` importuje się jako `"5907925017654"`), ale kod wklejony ręcznie /
z CSV / z komórki tekstowej trafia w bug. Test: `test_f3_excel_import_logic_and_float_ean`.
**Poprawka:** przy imporcie/`_on_generate` normalizować `^\d{13}\.0$` → 13 cyfr (lub ostrzegać).

### NISKI

**B-7. Martwy kod i nieużywany import w generator.py.**
`_count_data_modules` + `_PROBE_MW_MM`/`_PROBE_QZ_MM` — zero wywołań (w źródle nazwa występuje
tylko w definicji); `import time` nieużywany (jedyne „time" to `os.utime`). Dowód: analiza źródła
w teście `test_f5_dead_code_and_unused_import`. **Poprawka:** usunąć.

**B-8. Sieroty językowe — komunikaty generatora są TYLKO polskie, plus stringi poza `lang.py`.**
Dowód uruchomieniowy: `BarcodeError` = „Błędna suma kontrolna…", „Pusty kod" niezależnie od języka —
w EN UI log `[ERR]` pokazuje polski tekst. Pozostałe sieroty (statycznie): stopka
„Wszelkie prawa zastrzeżone © 2026 | by" (app.py:362), znaczniki `[OK]`/`[ERR]` (508/511),
filtry dialogu pliku „Excel files"/„All files" (393 — po angielsku w polskim UI), tytuł okna,
separator `─`, bullet `  • `, komunikaty „DPI musi być dodatnie", „Kod zawiera niedozwolone znaki…",
„EAN-13 musi mieć dokładnie 13 cyfr". Test: `test_f5_generator_errors_polish_only`.
**Poprawka:** przenieść komunikaty generatora do `lang.py` (np. kody błędów + tłumaczenie w UI).

**B-9. `scale="nan"` (rejestr lub pole entry) po cichu staje się 3.0 (maksimum).**
`float("nan")` przechodzi parsowanie, a łańcuch `max(0.5, min(3.0, nan))` zwraca 3.0 przez
semantykę porównań NaN. Dowód: `load_settings` z `scale="nan"` → 3.0; replika `_on_scale_entry`
`"nan"` → 3.0. Brak crasha, ale wartość zaskakująca (użytkownik wpisuje śmieć, dostaje maksymalny rozmiar).
Testy: `test_f3_registry_validation_and_migrations`, `test_f4_scale_entry_parse_logic`.
**Poprawka:** `if math.isnan(val): raise ValueError`.

**B-10. Przerwa „po 7. znaku" aplikowana też do Code128 ≥8 znaków.**
Dowód pomiarowy: `"ABCDEFGH12"` → przerwy `[5,7,8,7,9,6,`**`66`**`,10,11]` — dziura 2.2 cyfry w
środku tekstu alfanumerycznego. W kodzie opisane jako celowe („Applied universally"), ale wymaganie
klienta dotyczyło wyglądu EAN — dla Code128 wygląda to jak błąd składu. Test:
`test_f4b_code128_long_gets_the_gap_too`. **Poprawka:** stosować `_GAP_AFTER` tylko dla ean13.

**B-11. Limit 260 znaków ścieżki — zależny od maszyny.**
Kod 200 znaków + głęboki katalog (ścieżka 383 zn.) DZIAŁA tutaj, bo `LongPathsEnabled=1`
(odczyt z HKLM) + manifest Pythona 3.14. Na domyślnym Windows 10 (wartość 0) i w zbudowanym
`BarcodeGen.exe` (PyInstaller — manifest może nie mieć longPathAware) generacja się wysypie.
Test: `test_f2_200_char_code_long_path` (dokumentuje zachowanie na tej maszynie).
**Poprawka:** limit długości kodu (np. 128) albo prefiks `\\?\` przy zapisie.

**B-12. Kwantyzacja przy niskim DPI bez informacji zwrotnej.**
Przy dpi=72 dystanse 0.05/0.2/0.33/(≤0.7) mm dają IDENTYCZNE pliki (jeden hash, podłoga 2 px =
0.706 mm — ponad 2× więcej niż żądane 0.33). Zachowanie zgodne z projektem („crisp px"), ale UI
nigdzie nie mówi, że żądana szerokość została nadpisana. Test:
`test_f1_quantization_collapses_distances_at_72dpi`. **Poprawka:** log/status z efektywnym module_mm.

**B-13. `_open_settings` woła `win.grab_set()` natychmiast (app.py:574), choć `_open_help` odracza je z komentarzem, że natychmiastowe wywołanie na niepokazanym Toplevel potrafi rzucić (556).**
Niespójność — okno ustawień ma dokładnie ten race, przed którym broni się okno pomocy.
Niesprawdzalne automatycznie (wymaga realnego mapowania okien); ocena z kodu.

---

## Checklist wymagań klienta (pkt 27)

| Wymaganie | Werdykt | Dowód |
|---|---|---|
| Moduł (Szerokość modułu, mm) steruje szerokością kodu | ✅ | 62 kombinacje: zmierzony najwęższy pasek == wzór `max(2,round(d·s·dpi/25.4))` + podłoga 0.2 mm, 0 rozjazdów (`test_f1_matrix`); zastrzeżenie: kwantyzacja przy 72 dpi (B-12) |
| Czcionka absolutna (niezależna od wymiarów kodu) | ✅ | 5 konfiguracji (height 1→150, distance 5, scale 3) → glify **35 px co do piksela** (`test_f1_font_absolute_pixel_identical`) |
| Czcionka bez sufitu | ✅ | font_size=15 mm przy height=150 generuje się i dekoduje (macierz); target rośnie liniowo: 142 px @1200 dpi (`test_f1_font_mm_calibration_across_dpi`) |
| Skala tekstu w mm | ✅ | 3.0 mm → zmierzone 3.17/2.96/3.01 mm przy 72/300/1200 dpi (± 1 px kwantyzacji); migracja starej skali 12→20.3→15.0 działa (`test_f3_registry_validation_and_migrations`) |
| Tracking + przerwa po 7. znaku | ✅ | pomiar kolumn: przerwy `[5,7,9,11,7,6,67,12,6,6,6,5]` — 67 px po 7. znaku, tracking jednolity; <7 znaków nie psuje układu (`test_f4b_*`); zastrzeżenie B-10 dla długich Code128 |
| DPI wspólne, 300 działa | ✅ | dpi=300 domyślne w każdym teście generacji: 100% plików dekoduje 1:1; PNG zapisany z `dpi=(300,300)` |

---

## Niesprawdzalne automatycznie (i dlaczego)

- **Okna dialogowe** (kolizja nazw, duplikaty, nadpisanie, błędne parametry) — wymagają `mainloop()` i klikania; przetestowano SAMĄ logikę decyzji (testy F4).
- **`_rebuild_ui` po zmianie języka / „Przywróć domyślne"** — wymaga żywych widgetów CTk; z kodu: stan (kody, log, progress, licznik) jest jawnie przenoszony; ryzyko realne opisane w B-13 nie tu.
- **`_open_help` reuse okna** (podwójny klik) — logika `getattr(self,'_help_win')` + `winfo_exists()` wygląda poprawnie, ale `winfo_exists` wymaga działającego Tk.
- **Motyw dark↔light wizualnie**, `os.startfile` (otwiera realnego Explorera), zachowanie po skasowaniu folderu (kod: `hasattr` + `.exists()` → cichy brak akcji — poprawne, ale nieklikalne headless).
- **Zamknięcie aplikacji w trakcie generacji** — wątek `daemon=True` (app.py:515) ginie z procesem; możliwy częściowo zapisany PNG jeśli śmierć wypadnie w `final.save()`. Brak przycisku anulowania — ODNOTOWANE (istotne w połączeniu z B-1: 2-minutowe generacje bez możliwości przerwania).
