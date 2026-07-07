# QA_RAPORT_sonnet_2 — BarcodeGen v1.0.1 (commit e6fcdd9)

Niezależny, wrogi audyt QA. TAG = `sonnet_2`. Wszystkie wnioski poparte URUCHOMIENIEM
kodu (hashe SHA-256, dekodowanie zxing-cpp, pomiary pikseli z realnych obrazów, realne
odczyty/zapisy rejestru na izolowanym podkluczu, realne headless-uruchomienie
`customtkinter`/Tk na tym Windowsie — bez `mainloop()`).

## Środowisko

- Python 3.14.3, Windows 10, katalog roboczy `C:\Users\Super\projekty\BarcodeGen`.
- `pytest 9.1.1`, `zxingcpp`, `openpyxl`, `Pillow`, `python-barcode`, `numpy` (do pomiaru
  pikseli), `customtkinter` (import działa headless — **potrafi też tworzyć realne,
  niewidoczne okna Tk bez `mainloop()`**, co zweryfikowano eksperymentalnie i wykorzystano
  do kilku testów GUI zamiast czystej symulacji logiki).
- Rejestr izolowany: `Software\BarcodeGen_QA_sonnet_2` i `Software\BarcodeGen_QA_sonnet_2_gui`
  (tworzone i kasowane per test/fixture, prawdziwy klucz `Software\BarcodeGen` nietknięty).
- Wszystkie testy piszą wyłącznie do `tests/test_qa_audit_sonnet_2.py` i
  `QA_RAPORT_sonnet_2.md`, katalogi wyjściowe — własne `tempfile.mkdtemp()`.

## Wykonane testy + dowody

| # | Test | Dowód / liczba / hash |
|---|------|------------------------|
| 1 | Macierz 5 osi × ekstrema (dystans/font/wysokość/dpi/skala), EAN + Code128 | 30 kombinacji × 2 typy = 60 renderów, 0 błędów, wszystkie zdekodowane zxing na dokładny wejściowy kod, najwęższy pasek zmierzony w px == wzorowi z poprawką podłogi 0.2mm (0 rozbieżności / 60) |
| 2 | Czcionka absolutna, font_size=3mm, 5 konfiguracji (dpi=300 stałe) | zmierzona wysokość glifu identyczna co do piksela: **35px** we wszystkich 5 (height=1/9/150, distance=0.33/10, scale=1/3); kalibracja mm: oczekiwane round(3*300/25.4)=35px — dokładne trafienie |
| 3 | EAN-13, 20 poprawnych sum (własna implementacja Luhn-EAN) | 20/20 zdekodowane poprawnie przez zxing |
| 4 | EAN-13, 20 celowo zepsutych sum | 20/20 rzuca `BarcodeError` z poprawną oczekiwaną cyfrą kontrolną w treści |
| 5 | Code128 granice ASCII (32,126 dozwolone; 31,127 odrzucone; 1-znak; 80-znak; spacje wew.) | wszystkie 7 przypadków zgodne z oczekiwaniem, dozwolone zdekodowane poprawnie |
| 6 | `CON,PRN,NUL,com5,lpt9,Con,coM5` → pliki `_XXX.png` | `safe_filename` zwraca `_XXX`, plik fizycznie powstaje, rozmiar>0 (7/7) |
| 7 | `AB/CD` vs `AB?CD` kolizja nazw | `safe_filename` obu = `AB_CD` (potwierdzone `==`) |
| 8 | Nadpisanie pliku 2× | `st_mtime_ns` rośnie (`os.utime` wymusza aktualizację) |
| 9 | Kod 200 znaków | plik generuje się poprawnie (długa ścieżka >200 znaków); na tej maszynie (long paths) brak crasha — patrz „Niesprawdzalne”/uwagi środowiskowe |
| 10 | Rejestr: `language=DE→PL`, `theme=neon→dark`, `dpi=99999→1200`, `font_size=12` (bez `font_unit`) `→15.0`, `distance=0.15→0.33` | Każdy odczytany realnie z izolowanego podklucza rejestru — wartości dokładnie zgodne z opisem w brief |
| 11 | Rejestr: wszystkie pola naraz skorumpowane (`dpi=-5`, `font_size="abc"`, `scale=9999` itd.) | `load_settings()` nie rzuca wyjątku, wynik w granicach |
| 12 | Excel: int/text/formuła/pusty/data + 500 wierszy | 498 poprawnie odczytanych kodów, kolejność i typy zgodne z logiką `_import_excel` |
| 13 | Suwak skali: `"1,5"→1.5`, `"abc"→bez zmian`, `"0.1"→0.5`, `"99"→3.0` | zweryfikowane też na **realnym** `CTkEntry`/`CTkSlider` (headless GUI), identyczne wyniki co symulacja logiki |
| 14 | Ustawienia: `dpi=10000` w realnym oknie `_open_settings`, klik „Zapisz” | `messagebox.showerror` wywołany (zmockowany), `self.settings["dpi"]` pozostaje `300` |
| 15 | „Przywróć domyślne” w realnym oknie | `dpi 999→300`, `language EN→PL` po kliknięciu realnego przycisku |
| 16 | Przełączenie języka zachowuje stan | na realnym `App`: wpisane kody, log, progress bar, stan przycisku „Otwórz folder” — wszystko przetrwało `_toggle_lang()` |
| 17 | Okno pomocy — reużycie | `winfo_id()` identyczne przy 2. wywołaniu `_open_help()` na realnym Toplevel |
| 18 | Duplikaty → kolizja nazw (`AB/CD`×2 + `AB?CD`) | realny `_on_generate()`: 2 wywołania `askyesno` w kolejności (duplikat, potem kolizja), finalnie **1 plik** `AB_CD.png` (drugi kod nadpisał pierwszy — zgodnie z zaakceptowanym ostrzeżeniem) |
| 19 | Motyw dark→light | realny `_toggle_theme()`, odczyt z rejestru potwierdza zapisaną wartość `light` |
| 20 | Partia 10 kodów / 2 błędne | 8 plików powstało, dokładnie 2 błędy zarejestrowane (replika pętli `worker()`) |
| 21 | Odstępy tekstu — pomiar pikselowy | EAN-13: przerwa po 7. znaku = **67px** vs sąsiednie 5–12px (>3×); Code128 6-znakowy: brak wartości odstającej (5–11px) |
| 22 | `_resolve_output_dir`: pusty / zagnieżdżony / plik-zamiast-folderu | pusty→`.../output`; zagnieżdżony→`mkdir(parents=True)` działa; plik-jako-rodzic→`OSError` (łapane przez `_on_generate`) |
| 23 | Atak: emoji/unicode w Code128 | `BarcodeError` (oczekiwane) |
| 24 | Atak: EAN same zera z poprawną sumą | dekoduje się poprawnie |

Pełne dowody liczbowe (hashe, dokładne wartości) — patrz assercje w `tests/test_qa_audit_sonnet_2.py`.

## Znalezione błędy

### KRYTYCZNY

**K1 — Excel: EAN-13 z wiodącym zerem zapisany jako LICZBA traci zero i CICHO staje się Code128 (zła treść kodu, bez ostrzeżenia)**
- Dowód: w wygenerowanym pliku `.xlsx` komórka `int("0501234123456")` (poprawny 13-cyfrowy
  EAN z zerem wiodącym) zapisana jako liczba round-tripuje przez `openpyxl` jako
  `501234123456` (12 cyfr — zero ucięte). `_detect_barcode_type("501234123456")` zwraca
  `"code128"` (wymaga dokładnie 13 cyfr), więc `generate()` **nie rzuca żadnego wyjątku**
  — po prostu tworzy kod kreskowy Code128 kodujący ZŁĄ, 12-cyfrową liczbę zamiast EAN-13.
  Użytkownik nie dostaje żadnego komunikatu, że coś poszło nie tak (test
  `test_BUG_excel_ean_leading_zero_lost_when_stored_as_number`, PASS — dokumentuje
  aktualne zachowanie).
- To bardzo realny scenariusz: Excel domyślnie interpretuje wpisaną liczbę jako typ
  Liczba, nie Tekst, i zawsze usuwa wiodące zera.
- Propozycja poprawki: w `_import_excel` wykrywać komórki typu `int`/`float`, których
  `str()` ma mniej niż 13 znaków a sąsiednie/inne komórki w kolumnie mają 13 — a
  przynajmniej: gdy zaimportowany „kod” ma 12 cyfr, ostrzec w logu / GUI
  („ten kod ma 12 cyfr — czy to obcięty EAN-13? sprawdź kolumnę Excela”), zamiast
  cichego przejścia na Code128.

**K2 — Kod z artefaktem „.0” (typowy dla ścieżek liczba→string) cicho staje się Code128 kodującym dosłowną kropkę**
- Dowód: `"5907925017654.0"` (15 znaków) → `_detect_barcode_type` = `"code128"` →
  wygenerowany plik dekoduje się przez zxing dokładnie jako tekst `"5907925017654.0"`
  (z kropką!) — żadnego wyjątku, żadnego ostrzeżenia (test
  `test_BUG_excel_ean_trailing_dot_zero_silently_becomes_code128`).
- To ten sam rodzaj błędu co K1 — cichy fallback EAN→Code128 bez żadnej walidacji „czy
  to w ogóle wygląda jak popsuty EAN”. Razem K1+K2 pokazują, że jakikolwiek artefakt
  liczbowy z Excela/pandas w polu EAN-13 przechodzi bez ostrzeżenia jako inny typ kodu.
- Propozycja poprawki: dodać heurystykę „kod zawiera same cyfry + max jedną kropkę na
  końcu i ma 13-14 znaków” → ostrzeżenie o prawdopodobnie zepsutym EAN, zamiast cichego
  Code128.

**K3 — PARAM_RANGES maksima (każde z osobna „bezpieczne”) w kombinacji dają obraz ~2,9 gigapiksela — dokładnie to, czemu komentarz w kodzie mówi że zapobiega**
- Dowód: `app.py` linia 41-42 wprost mówi: „Prevents e.g. dpi=10000 + height=1000 from
  generating a multi-gigapixel image that hangs or crashes the app”. Ale
  `height=150` (max), `distance=10` (max), `font_size=15` (max), `dpi=1200` (max),
  `scale=3.0` (max) — **wszystkie w granicach `PARAM_RANGES`** — dają canvas
  **2 887 680 066 pikseli**, co przekracza limit „decompression bomb” Pillowa i rzuca
  `PIL.Image.DecompressionBombError` (test
  `test_ATTACK_param_ranges_max_combo_triggers_decompression_bomb`, PASS).
- Wyjątek jest łapany przez generyczny `except Exception` w `worker()`, więc apka się
  nie wywala — ale użytkownik dostaje nieprzetłumaczony, techniczny komunikat Pillow
  zamiast czytelnego polskiego błędu, a intencja komentarza (uniknięcie
  wielogigapikselowego obrazu) jest jawnie niespełniona.
- Dodatkowy dowód na realność ryzyka (nie tylko na granicy): kombinacja WYRAŹNIE
  poniżej maksimów (`height=100, distance=3, font_size=15, dpi=800, scale=2.0`) daje
  już **126 megapikseli i ~2,9s na JEDEN kod** (test
  `test_ATTACK_large_but_in_range_combo_is_slow`). Przy limicie 100 kodów w jednej
  partii i braku przycisku anulowania (patrz FAZA 4 pkt 15/16) to realne ryzyko
  kilkuminutowego zawieszenia UI.
- Propozycja poprawki: dodać dodatkowy, wspólny limit „powierzchnia całkowita w px”
  (np. `width*height <= N`) liczony PRZED renderowaniem (z estymacji modułów i
  wysokości), niezależny od pojedynczych zakresów height/distance/font/dpi/scale.

### ŚREDNI

**Ś1 — „Szerokość modułu” (distance) nie ma żadnego efektu w paśmie 0.05–0.25mm przy dpi=300**
- Dowód: `distance` = 0.05, 0.1, 0.15, 0.2, 0.21, 0.22, 0.25mm przy dpi=300, scale=1 dają
  **identyczny hash SHA-256 pliku** (`4474da0af59e...`) — podłoga 0.2mm w kodzie
  (`_render.generate`, sekcja „1. Module size”) zaokrągla wszystkie te wartości do tego
  samego 3px modułu. Dopiero 0.33mm (domyślna wartość) daje inny wynik (test
  `test_BUG_distance_dead_zone_0_05_to_0_25mm_at_dpi300`).
- Zakres `PARAM_RANGES["distance"] = (0.05, 10.0)` sugeruje, że 0.05–0.25mm to
  poprawne, użyteczne wartości — w praktyce cały ten fragment suwaka/pola jest martwy
  przy domyślnym DPI.
- Propozycja: albo podnieść dolną granicę `PARAM_RANGES["distance"]` do realistycznej
  (np. 0.2mm, zgodnie z komentarzem „scanner/library minimum”), albo w UI pokazywać
  ostrzeżenie/wskazówkę gdy wybrana wartość i tak zostanie podniesiona do podłogi.

**Ś2 — „Wysokość tekstu” (font_size) nie ma żadnego efektu w paśmie 0.5–2.2mm przy dpi=72**
- Dowód: `font_size` = 0.5, 1.0, 1.5, 2.0, 2.2mm przy dpi=72 dają **identyczny hash**
  (`4232c77d5188...`) — `target_text_h = max(6, round(font_size*dpi/25.4))` osiąga
  podłogę 6px dla całego tego pasma; dopiero 2.5mm daje inny wynik (test
  `test_BUG_font_size_dead_zone_0_5_to_2_2mm_at_dpi72`).
- To dokładnie ten sam wzorzec co Ś1 — działa poprawnie przy dpi=300 (patrz test
  „font absolute identyczny px”), ale przy niskim DPI (72, wciąż w dozwolonym zakresie
  DPI 72-1200!) duży fragment zakresu font_size jest martwy.
- Propozycja: podnieść podłogę `max(6, ...)` proporcjonalnie do dpi, albo ostrzegać w
  UI przy niskim DPI.

**Ś3 — `generate()` nie chroni się przed ujemnym `height`/`scale` — surowy `ValueError` zamiast `BarcodeError`**
- Dowód: `G.generate(code, height=-5, ...)` i `G.generate(code, scale=-1, ...)` rzucają
  `ValueError: Width and height must be >= 0` (z Pillow), NIE `BarcodeError` (test
  `test_ATTACK_negative_height_or_scale_bypasses_generate_and_crashes_with_ValueError`).
  Dla porównania: `distance` ujemne NIE crashuje, bo kod ma jawną ochronę
  `max(0.05, distance)` (linia 268) — `height` i `scale` takiej ochrony nie mają.
- W obecnym GUI to nieosiągalne (suwak i `PARAM_RANGES` nie pozwalają na ujemne
  wartości), ale `BarcodeGenerator.generate()` jest oznaczony w komentarzu jako
  „Public API” — więc kontrakt tej funkcji jest niespójny: jeden parametr ma ochronę,
  dwa inne nie.
- Propozycja: dodać analogiczny `max(...)` guard dla `height` i `scale` w `generate()`,
  albo jawnie walidować i rzucać `BarcodeError` dla `height<=0`/`scale<=0`, tak jak już
  zrobiono dla `dpi<=0`.

**Ś4 — Wszystkie komunikaty `BarcodeError` są na sztywno po polsku, niezależnie od wybranego języka UI**
- Dowód: `generator.py` — każdy `raise BarcodeError(f"...")` to zaszyty polski string
  (linie 72, 76-78, 243, 245, 258-260). Test
  `test_BUG_all_barcode_error_messages_are_hardcoded_polish_regardless_of_ui_language`
  potwierdza treść „Błędna suma kontrolna...” niezależnie od `self.lang`.
- Skutek: użytkownik w trybie EN i tak widzi polskie komunikaty błędów w logu
  (`[ERR] {code} — {err}`), co przeczy całej idei przełącznika języka dla tej — dość
  częstej w praktyce (błędne sumy EAN, złe znaki Code128) — części UI.
- Propozycja: przenieść treści błędów do `lang.py` (parametryzowane) albo dodać
  osobny słownik komunikatów błędów per język w `generator.py`.

**Ś5 — Batch do 100 kodów bez przycisku anulowania, przy realistycznie osiągalnych parametrach generacja jednego kodu może trwać kilka sekund**
- Dowód: patrz K3 — 126 megapikselowy obraz (parametry WYRAŹNIE poniżej maksimów) to
  ~2,9s na kod. 100 takich kodów w jednej partii (dozwolone przez `too_many` check
  `len(codes) > 100`) to potencjalnie ~5 minut zawieszenia wątku roboczego bez żadnej
  możliwości przerwania (funkcjonalność `daemon thread` bez `cancel` — zgodnie z
  FAZA 4 pkt 15/16 z brief, tu z twardym pomiarem czasu).
- Propozycja: dodać limit powierzchni obrazu (patrz K3) ORAZ przycisk anulowania
  ustawiający flagę sprawdzaną w pętli `worker()`.

### NISKI

**N1 — Martwy kod: `_count_data_modules` (+ `_PROBE_MW_MM`/`_PROBE_QZ_MM`) nigdy nie jest wywoływany**
- Dowód: `inspect.getsource(BarcodeGenerator.generate)` nie zawiera
  `_count_data_modules`; `grep` po całym `app.py` też nic nie znajduje (test
  `test_count_data_modules_is_dead_code`, PASS). Funkcja i dwie stałe istnieją, ale są
  całkowicie nieosiągalne — dokładnie ten wzorzec, przed którym ostrzega brief audytu
  („parametr, który wyglądał na podpięty, a nic nie robił”).
- Propozycja: usunąć martwy kod albo — jeśli miał służyć do walidacji szerokości modułów
  — dopiąć go i pokryć testem regresyjnym.

**N2 — Stopka „Wszelkie prawa zastrzeżone © 2026” zawsze po polsku, niezależnie od języka UI**
- Dowód: string zaszyty w `app.py` (`_build_footer`, linia 362), nieobecny w żadnym z
  kluczy `LANG["EN"]` (test
  `test_footer_copyright_string_is_hardcoded_polish_outside_lang_py`).
- Propozycja: przenieść do `lang.py` jako klucz `footer_copyright`.

**N3 — `_open_output_folder` po skasowaniu folderu wyjściowego cicho nic nie robi (brak feedbacku)**
- Dowód: po `shutil.rmtree(out_dir)` wywołanie logiki `_open_output_folder` daje pustą
  listę akcji — `.exists()` chroni przed crashem, ale użytkownik klikający „Otwórz
  folder wyników” nie dostaje ŻADNEJ informacji, że nic się nie stało (test
  `test_open_output_folder_logic_noop_after_folder_deleted`).
- Propozycja: pokazać `messagebox.showwarning` gdy folder nie istnieje.

**N4 — Gap-po-7-znaku stosowany też do długich kodów Code128 (≥8 znaków)**
- Dowód: kod Code128 `"ABCDEFGH"` (8 znaków) ma zmierzoną przerwę po 7. glifie = 66px vs
  sąsiednie ~6-8px — ten sam efekt co w EAN-13 (test
  `test_gap_after_7th_char_also_applies_to_long_code128`). To udokumentowane w
  kodzie jako celowe (komentarz „Applied universally to any code”), więc NIE zgłaszam
  tego jako bug, tylko jako obserwację projektową: dowolny 8+ znakowy numer części
  Code128 dostaje wizualnie „EAN-owy” podział, co może wyglądać nieoczekiwanie dla
  danych niebędących EAN-em.

**N5 — Nieużywane pliki `*_backup_20260703.*` w katalogu głównym repo (nie w `.gitignore`)**
- Dowód: `generator_backup_20260703.py` (258 linii) vs `generator.py` (345 linii),
  `app_backup_20260703.py` (560 vs 738 linii), `lang_backup_20260703.py` (80 vs 186
  linii) oraz kilka `icon_backup*.ico/png` — wszystkie realnie leżą w repo, nic ich
  nie importuje (potwierdzone `grep`), ale mogą mylić przy przyszłych zmianach
  (przypadkowa edycja niewłaściwego pliku). Nie jest to błąd runtime.

## Tabela checklist wymagań klienta

| Wymaganie klienta | Status | Dowód |
|---|---|---|
| Moduł steruje szerokością kodu | **DZIAŁA (z zastrzeżeniem Ś1)** | test macierzy: szerokość rośnie z `distance` (0.33→10mm daje różne hashe/szerokości); ALE pasmo 0.05-0.25mm przy dpi=300 jest martwe (patrz Ś1) |
| Czcionka absolutna (niezależna od wymiarów kodu) | **DZIAŁA** | `test_font_size_absolute_identical_px_across_configs`: 35px identyczne przy 5 różnych height/distance/scale |
| Czcionka bez sufitu (rośnie liniowo, bez capu) | **DZIAŁA** (potwierdzone też w istniejącym `test_scaling.py`, nie modyfikowanym) | wysokość tekstu rośnie z font_size bez ograniczenia górnego w zakresie testowanym |
| Skala tekstu w mm | **DZIAŁA** (z zastrzeżeniem Ś2) | `font_size` interpretowany jako mm (`target_text_h = font_size*dpi/25.4`); ALE pasmo 0.5-2.2mm przy dpi=72 jest martwe |
| Tracking + przerwa po 7. znaku | **DZIAŁA** | pomiar pikselowy: przerwa po 7. glifie EAN-13 = 67px vs 5-12px sąsiednie (>3×); Code128 <7 znaków bez wartości odstającej |
| DPI wspólne 300 działa | **DZIAŁA** | cała macierz przy dpi=300 (i 72, 1200) dekoduje się poprawnie, 0 błędów na 60 renderów |

## Niesprawdzalne automatycznie

- **Wygląd wizualny okna ustawień/motywu jasny/ciemny** (rzeczywisty render kolorów) —
  logika zapisu do rejestru i `ctk.set_appearance_mode()` zweryfikowana realnie
  (headless), ale faktyczny wygląd pikseli motywu wymaga wizualnej inspekcji człowieka.
- **Zamknięcie aplikacji w trakcie generacji** (pkt 16 z brief) — wątek roboczy jest
  `daemon=True`, więc ginie z procesem przy zamknięciu głównego okna; zachowanie to
  potwierdzone przez samą naturę wątków daemon w Pythonie, ale nie da się „zaobserwować”
  zamknięcia okna bez prawdziwego zamknięcia procesu w trakcie testu (ryzykowne dla
  stabilności test suite) — oceniono z kodu, nie uruchomiono na żywo.
- **Rzeczywisty scroll/interakcja myszką na suwaku `CTkSlider`** — testowano
  programowe wywołanie `_on_scale_slider`/`_on_scale_entry`, nie fizyczny drag myszą
  (nie ma to znaczenia dla logiki, ale jest to interakcja czysto sprzętowa).
- **200-znakowy kod i limit ścieżki Windows 260 znaków** — na TEJ maszynie (long paths
  najwyraźniej włączone) test przeszedł nawet przy ścieżce >650 znaków. Na maszynie
  klienta z wyłączonym „long path support” może to się zachowywać inaczej — flagowane
  jako ryzyko zależne od środowiska, nie jako potwierdzony bug.

## Podsumowanie liczbowe

- **KRYTYCZNY: 3** (K1 cichy EAN→Code128 przy wiodącym zerze z Excela, K2 cichy
  EAN→Code128 przy artefakcie „.0”, K3 PARAM_RANGES maksima dają decompression bomb)
- **ŚREDNI: 5** (Ś1 martwa strefa distance @dpi300, Ś2 martwa strefa font_size @dpi72,
  Ś3 brak ochrony height/scale w `generate()`, Ś4 błędy zawsze po polsku, Ś5 batch bez
  cancel + realistyczny czas generacji)
- **NISKI: 5** (N1 martwy kod `_count_data_modules`, N2 stopka zawsze PL, N3 cichy
  no-op „Otwórz folder”, N4 gap-po-7 na długich Code128 — obserwacja projektowa, N5
  pliki backup w repo)

`pytest tests/test_qa_audit_sonnet_2.py -v` → **54 passed** (testy dokumentujące bugi
asertują AKTUALNE, błędne zachowanie — patrz nazwy `test_BUG_*` i `test_ATTACK_*`).
