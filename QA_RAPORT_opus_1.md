# QA RAPORT — BarcodeGen v1.0.1 (przebieg TAG = opus_1)

Niezależny, wrogi audyt. Każdy wniosek oparty na **uruchomionym kodzie**
(dekoder zxing-cpp, pomiary pikseli z obrazu, hashe plików, treści wyjątków).
Testy: `tests/test_qa_audit_opus_1.py` — **46 passed**.

## Środowisko
- Python 3.14.3, Windows 10 (19045), katalog `c:\Users\Super\projekty\BarcodeGen`.
- `import app` (customtkinter) działa headless — nie potrzeba `mainloop()`.
- Dekoder: `zxingcpp.read_barcodes(PIL_Image)`. Pomiary glifów/pasków: `numpy` na obrazie w skali szarości.
- Izolacja rejestru: `app.REG_KEY = r"Software\BarcodeGen_QA_opus_1"`, usunięty po testach (potwierdzone: podklucz `absent`). Prawdziwy `Software\BarcodeGen` **nietknięty**.
- Katalogi wyjściowe: `tempfile.mkdtemp()`. Nie zapisywano do `dist/output`.

---

## Wykonane testy + dowody

| Obszar | Test / dowód | Wynik |
|---|---|---|
| F1 Macierz param. (7 skrajnych kombinacji) | plik>0B, zxing==kod, 7/7 unikatowych hashy, najwęższy pasek == `max(2,round(max(0.05,d)·s·dpi/25.4))` z podłogą 0.2 mm | OK |
| F1 Najwęższy pasek | zmierzono px == formuła dla d∈{0.05,0.2,0.33,1,10}, dpi∈{72,300,1200} (np. d0.05/dpi1200→10px, d0.33/dpi300→4px, d10/dpi300→118px) | OK |
| F1 Czcionka absolutna | font_size=3, 5 konfig. (height/distance/scale), dpi=300 → glif **35 px identyczny** we wszystkich; ≈ 3·300/25.4=35.4 ±2 | OK |
| F1 Czcionka vs dpi | font_size=3: 72→9px, 300→35px, 1200→142px (= round(3·dpi/25.4)) | OK |
| F1 EAN-13 poprawne | 20 losowych (suma z własnej impl.) → 20/20 dekodują | OK |
| F1 EAN-13 zła suma | 20 zepsutych → 20/20 `BarcodeError` z **poprawną oczekiwaną cyfrą** | OK |
| F1 EAN wiodące zera | `0000000000000`, `0075678164125` → dekodują 1:1 | OK |
| F1 Code128 granice | ASCII 32 i 126 → generują i dekodują; 31 i 127 → `BarcodeError` | OK |
| F1 Code128 długości | 1-znak, 80-znak, `AB   CD` (spacje w środku) → dekodują 1:1; same spacje → „Pusty kod" | OK |
| F2 Nazwy zarezerwowane | `CON/PRN/NUL/com5/lpt9` → `_CON.png`…, plik fizycznie istnieje, rozmiar>0 | OK |
| F2 Kolizja nazw | `AB/CD` i `AB?CD` → oba `AB_CD` (kolizja); logika `_on_generate` wykrywa grupę | OK |
| F2 Nadpisanie mtime | 2× ten sam kod → `st_mtime_ns` rośnie | OK |
| F2 Kod 200 znaków | plik powstaje (nawet w katalogu głębokim >260 znaków — long path działa) | OK |
| F3 Migracje rejestru | DE→PL, neon→dark, dpi99999→1200, font12(bez unit)→15.0, distance0.15→0.33, scale5→3.0, distance0.02→0.05, height-5→1.0, dpi"300.0"→300 | OK |
| F3 Import Excel | int/float/tekst/data→str, `None` i formuła(`data_only`=None) pominięte → lista dokładnie jak oczekiwano | OK |
| F4 Duplikaty (logika) | `[ABC,ABC,XYZ,ABC,XYZ]` → dupes `[ABC,XYZ]`, unique `[ABC,XYZ]` | OK |
| F4 Walidacja dpi=10000 | `not (72<=10000<=1200)` → odrzucone | OK |
| F4 Suwak skali parse | `"1,5"→1.5`, `"0.1"→0.5`, `"99"→3.0`, `"2.55"→2.5`, `"abc"→ValueError(restore)` | OK |
| F4b Partia z błędem | 10 kodów, 2 złe sumy → 8 plików, dokładnie 2 błędy z powodami | OK |
| F4b Przerwa po 7. znaku | EAN: 13 glifów, przerwa po 7. = **67 px** vs pozostałe ~7 px (>3× max) | OK |
| F4b Code128 <7 znaków | `ABC12`: 5 glifów, brak sztucznej przerwy (max gap <20 px) | OK |
| F4b Folder wyjściowy | pusty→`<app_dir>/output`; nieistniejący→mkdir(parents); zły dysk→OSError (łapany w `_on_generate`) | OK |

---

## Znalezione błędy

### [ŚREDNI] Kombinacja parametrów w pełni dozwolona przez `PARAM_RANGES`+suwak wysadza generację (DecompressionBombError)
- **Opis**: `distance=10` (max w `PARAM_RANGES`), `dpi=1200` (max), `scale=3.0` (max suwaka) — wszystkie ustawialne przez GUI — dają obraz ~185 mln px (a przy `height=150`: ~2,89 mld px), co przekracza limit PIL 178 956 970 px.
- **Dowód** (uruchomienie): `gen.generate(code="5901234123457", distance=10, dpi=1200, scale=3.0, height=9)` →
  `PIL.Image.DecompressionBombError: Image size (185263730 pixels) exceeds limit of 178956970 pixels`. **Nie** jest to `BarcodeError` (`isinstance(..., BarcodeError) == False`).
- **Skutki**: w partii `worker()` łapie to jako `except Exception` i loguje `[ERR] <kod> — Image size (...) exceeds limit...` — komunikat surowy, **po angielsku**, nieczytelny dla użytkownika. Komentarz nad `PARAM_RANGES` twierdzi wprost, że zakresy „*Prevents e.g. dpi=10000 + height=1000 from generating a multi-gigapixel image that hangs or crashes the app*" — a jednak przy maksymalnych dozwolonych wartościach obraz właśnie przekracza limit.
- **Proponowana poprawka**: w `generator.generate()` po wyliczeniu `canvas_w`/`canvas_h` sprawdzić iloczyn i rzucić czytelny `BarcodeError` (np. „Obraz zbyt duży: {w}×{h}px — zmniejsz DPI / rozmiar / szerokość modułu"), zanim `_render_bars` wywoła PIL. Alternatywnie zacieśnić `PARAM_RANGES` (np. `distance ≤ 3`) lub liczyć realny limit px z iloczynu `distance·scale·dpi·liczba_modułów`.

### [NISKI] Martwy kod: `_count_data_modules` + stałe `_PROBE_MW_MM`/`_PROBE_QZ_MM`
- **Opis**: funkcja `_count_data_modules` (generator.py:185) i towarzyszące stałe nie są nigdzie wywoływane.
- **Dowód**: `src.count("_count_data_modules(") == 1` (tylko definicja). Grep w repo potwierdza brak wywołań (poza plikiem `*_backup_*`).
- **Poprawka**: usunąć funkcję i stałe `_PROBE_*` (dead code, mylące przy utrzymaniu).

### [NISKI] Martwy import `import time` w `generator.py`
- **Opis**: `import time` (linia 19) nieużywany (`time.` nie występuje w pliku). Znacznik czasu ustawiany jest przez `os.utime`, nie `time`.
- **Dowód**: `"time." not in src == True`.
- **Poprawka**: usunąć import.

### [NISKI, i18n] Komunikaty `BarcodeError` wyłącznie po polsku — widoczne także w trybie EN
- **Opis**: wszystkie wyjątki z `generator.py` mają teksty PL („Błędna suma kontrolna EAN-13…", „Kod zawiera niedozwolone znaki…", „Pusty kod", „DPI musi być dodatnie…"). Trafiają do logu `[ERR]` niezależnie od wybranego języka — w trybie EN użytkownik widzi polskie komunikaty.
- **Dowód**: teksty PL obecne w źródle; brak wariantów EN. W `_on_generation_done`/`worker` `str(e)` wstawiany do logu bez tłumaczenia.
- **Poprawka**: albo kody błędów + mapowanie w `lang.py`, albo przekazywać `self.t` do generatora. Minimalnie: udokumentować jako znaną ograniczoną lokalizację.

### [NISKI, i18n] Stringi UI poza `lang.py` (sieroty tłumaczeniowe)
- **Opis / dowód** (odczyt źródła app.py):
  - Stopka: `"Wszelkie prawa zastrzeżone © 2026  |  by "`, `"dCoded"`, `" & "`, `"id3ntity"` — zaszyte, nieprzełączalne PL/EN.
  - Tagi logu `"[OK] {c}"`, `"[ERR] {c} — {err}"` — literały (akceptowalne jako stałe techniczne, ale nie w `lang.py`).
  - Separator `"─" * 40`, `APP_NAME`, tytuł okna — zaszyte (kosmetyczne).
- **Poprawka**: przenieść widoczny tekst stopki do `LANG`, jeśli wymagana pełna lokalizacja.

### [NISKI] `generate()` nie waliduje własnych parametrów numerycznych — surowy `ValueError` / niedekodowalny obraz
- **Opis**: dla `height<0` python-barcode rzuca surowy `ValueError: Width and height must be >= 0` (nie `BarcodeError`); dla `height=0` powstaje obraz **bez pasków** (zxing zwraca `None` — niedekodowalny), bez żadnego ostrzeżenia. Z GUI niedostępne (clamp `PARAM_RANGES`/suwak), ale `BarcodeGenerator.generate` jest publiczne i wywoływalne z dowolnymi wartościami.
- **Dowód**: `height=-5` → `ValueError` (nie BarcodeError); `height=0` → plik istnieje, `zxingcpp.read_barcodes` → pusta lista.
- **Poprawka**: na wejściu `generate()` walidować `height>0`, `scale>0` i rzucać `BarcodeError` z czytelnym komunikatem (spójnie z istniejącym guardem `dpi<=0`).

### [NISKI] 13-cyfrowy EAN z sufiksem `.0` (float z Excela) cicho staje się Code128
- **Opis**: `"5907925017654.0"` (postać, jaką przyjmuje liczba zmiennoprzecinkowa) → `_detect_barcode_type` = `code128`, generuje kod zawierający literalnie `.0`, **nie** EAN-13, bez ostrzeżenia o zgubionej sumie kontrolnej.
- **Dowód**: `_detect_barcode_type("5907925017654.0")=="code128"`; wygenerowany kod dekoduje się do `"5907925017654.0"`.
- **Uwaga łagodząca**: w ścieżce importu Excela `openpyxl` zwraca **int** dla liczb całkowitych (`5907925017654.0` → `5907925017654`), więc realny import daje poprawny EAN. Ryzyko dotyczy wpisania ręcznego lub innych źródeł danych.
- **Poprawka**: przed detekcją typu normalizować `"<cyfry>.0"` → `"<cyfry>"` (usuwać zerowy ułamek), lub ostrzegać, gdy 12–14 cyfr + `.0`.

---

## Tabela checklist wymagań klienta (pkt 27)

| Wymaganie | Status | Dowód (test) |
|---|---|---|
| Moduł steruje szerokością | SPEŁNIONE | `test_ean13_matrix…`: najwęższy pasek px == `f(distance,scale,dpi)`; d10/dpi300→118px vs d0.05→3px |
| Czcionka absolutna (niezależna od wymiarów) | SPEŁNIONE | `test_font_absolute_identical_px_same_dpi`: 5 konfig. → **35 px identyczny** |
| Czcionka bez sufitu (rośnie liniowo) | SPEŁNIONE | font_size=15@1200dpi=708px, font_size=1000@72dpi generuje (3015×1469); brak capa poza wewn. binary-search hi=2000 (nieosiągalny w zakresach) |
| Skala tekstu w mm | SPEŁNIONE | `test_font_scales_with_dpi`: glif ≈ font_size·dpi/25.4 ±2 (3mm@300=35px) |
| Tracking + przerwa po 7. znaku | SPEŁNIONE | `test_gap_after_7th_char`: przerwa 67px vs ~7px; Code128<7 bez artefaktu |
| DPI wspólne 300 działa | SPEŁNIONE | cała macierz przy dpi=300 dekoduje; domyślne `DEFAULT_SETTINGS["dpi"]=300` |

---

## Niesprawdzalne automatycznie (wymagają manualnego GUI)
- **Pkt 11 (settings `_save`)**: samą logikę zakresu przetestowano (`test_dpi_range_validation_logic`), ale wyświetlenie `messagebox` i **brak zapisu przy błędzie** wymaga interakcji z oknem — kod: przy `ValueError` `save_settings` nie jest wołane, wartość nie zapisana (ocena z kodu).
- **Pkt 12/20/24 (okna kolizji/duplikatów, wpis w suwaku)**: przetestowano logikę wykrywania i parsowania; same `askyesno`/bind zdarzeń — manualne.
- **Pkt 13 (zachowanie kodów przy zmianie języka, `_rebuild_ui`)**: logika zachowuje `preserved`/`log_text`/`progress`/`_last_result`; realne odtworzenie widżetów wymaga `mainloop` — manualne. Sieroty językowe wypisane wyżej.
- **Pkt 15/16 (wątek daemon, brak anulowania)**: `threading.Thread(daemon=True)` — brak przycisku „Anuluj" (odnotowane); wątek daemon ginie z procesem przy zamknięciu (ocena z kodu).
- **Pkt 23 (`_open_output_folder`)**: `os.startfile` + guard `.exists()` — gdy folder skasowany, funkcja nic nie robi (ocena z kodu); `os.startfile` niesprawdzalny headless.
- **Pkt 25/26 (motyw, reuse okna pomocy)**: `_toggle_theme` zapisuje motyw w rejestrze (logika OK); `_open_help` reużywa `self._help_win` przez `winfo_exists()` — poprawne (ocena z kodu), ale wymaga GUI do potwierdzenia braku 2. okna.
