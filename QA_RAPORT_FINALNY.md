# QA RAPORT FINALNY — BarcodeGen v1.0.1 (commit e6fcdd9)

**Konsolidacja 4 niezależnych, wrogich przebiegów QA** wykonanych na różnych modelach
(Opus, Sonnet, Haiku, Fable), każdy w pełnej izolacji (osobny plik raportu i testów,
osobny podklucz rejestru `Software\BarcodeGen_QA_<tag>`, osobne katalogi tymczasowe,
zakaz czytania cudzych wyników). Konsolidator (Opus) **ponownie zweryfikował uruchomieniem**
każde znalezisko unikatowe i każdą rozbieżność werdyktu — nie stosowano głosowania większości.

| | |
|---|---|
| Data | 2026-07-07 |
| Środowisko | Python 3.14.3, Windows 10 Home 19045, Pillow 12.2.0, python-barcode 0.16.1 |
| Dekoder weryfikujący | `zxing-cpp` 3.1.0 (`zxingcpp.read_barcodes`) |
| Suita testów (wszystkie) | **`pytest tests/` → 163 passed, 1 skipped** (test_scaling + 4 pliki QA) |
| Kod aplikacji | `app.py` / `generator.py` / `lang.py` — **niezmodyfikowane**; poprawki NIE wdrożone (do decyzji) |

---

## 1. Macierz: znalezisko × model (kto wykrył)

Legenda: ● wykrył · ○ pominął · ⚠ wykrył, ale z błędną wagą/opisem (rozstrzygnięto niżej).
Kolumna **Werdykt** = niezależna weryfikacja konsolidatora (uruchomienie).

| # | Znalezisko | opus_1 | sonnet_2 | haiku_3 | fable_4 | Werdykt (waga finalna) |
|---|---|:--:|:--:|:--:|:--:|---|
| K1 | **Excel: EAN-13 z wiodącym zerem → liczba gubi 0 → cicho Code128 ze złą treścią** | ○ | ● | ○ | ○ | **POTWIERDZONY — KRYTYCZNY** |
| Ś1 | PARAM_RANGES maks. → obraz ~2,9 Gpx → `DecompressionBombError` (komentarz w kodzie kłamie) | ● | ● | ○ | ● | **POTWIERDZONY — ŚREDNI (wysoki)** |
| Ś2 | Nazwa urządzenia z rozszerzeniem (`con.x`, `nul.x`, `aux.data`) → surowy crash, brak pliku | ○ | ○ | ○ | ● | **POTWIERDZONY — ŚREDNI** |
| Ś3 | Cyfry arabsko-indyjskie (`٥٩٠…`) przechodzą `isdigit()` → kod koduje INNE (ASCII) cyfry niż wpisane, log `[OK]` | ○ | ○ | ○ | ● | **POTWIERDZONY — ŚREDNI** |
| Ś4 | Quiet zone przycięta do ~1 modułu (norma EAN-13: ≥11) — ryzyko nieskanowalności wydruku „na styk” | ○ | ○ | ○ | ● | **POTWIERDZONY — ŚREDNI** |
| Ś5 | Martwa strefa `distance` 0.05–0.25 mm @ dpi=300 → identyczny hash (moduł ≠ szerokość na dolnym końcu suwaka) | ○ | ● | ○ | ●¹ | **POTWIERDZONY — ŚREDNI** |
| N1 | `²` (indeks górny) → `isdigit()`=True, len 13 → `int()` rzuca surowy `ValueError`, nie `BarcodeError` | ○ | ○ | ○ | ● | **POTWIERDZONY — NISKI** |
| N2 | EAN z artefaktem `.0` (`"5907925017654.0"`) → cicho Code128 | ●(N) | ⚠(K2) | ○ | ⚠(Ś) | **POTWIERDZONY — NISKI** (główna ścieżka Excela bezpieczna) |
| N3 | `generate()` nie waliduje `height`/`scale`<0 → surowy `ValueError`; `height=0` → obraz niedekodowalny bez ostrzeżenia | ● | ● | ○ | ○ | **POTWIERDZONY — NISKI** (API; GUI clampuje) |
| N4 | Komunikaty `BarcodeError` na sztywno po polsku — widoczne też w trybie EN | ● | ⚠(Ś) | ○ | ● | **POTWIERDZONY — NISKI** |
| N5 | Stopka „Wszelkie prawa zastrzeżone © 2026…” zaszyta po polsku, poza `lang.py` | ● | ● | ⚠(Ś) | ● | **POTWIERDZONY — NISKI** (konsensus 4/4) |
| N6 | Martwy kod: `_count_data_modules` + `_PROBE_*` nigdy nie wołane; `import time` nieużywany | ● | ● | ○ | ● | **POTWIERDZONY — NISKI** |
| N7 | Martwa strefa `font_size` 0.5–2.2 mm @ dpi=72 → identyczny hash | ○ | ● | ○ | ●¹ | **POTWIERDZONY — NISKI** (tylko przy nietypowym dpi=72) |
| N8 | `scale="nan"` (rejestr/pole) → cicho 3.0 (semantyka porównań NaN) | ○ | ○ | ○ | ● | **POTWIERDZONY — NISKI** |
| N9 | Przerwa „po 7. znaku” aplikowana też do Code128 ≥8 znaków | ○ | ●(obs.) | ○ | ● | **POTWIERDZONY — NISKI** (celowe wg komentarza) |
| N10 | `_open_output_folder` po skasowaniu folderu → cichy no-op bez feedbacku | ○ | ● | ○ | ○ | **POTWIERDZONY — NISKI** |
| N11 | `_open_settings` woła `grab_set()` natychmiast, choć `_open_help` odracza je (ten sam race) | ○ | ○ | ○ | ● | **POTWIERDZONY — NISKI** (obserwacja z kodu) |
| N12 | Pliki `*_backup_20260703.*` w katalogu repo, poza `.gitignore` | ○ | ● | ○ | ○ | **POTWIERDZONY — NISKI** (higiena repo) |
| N13 | `distance=0.15` ustawione świadomie przez użytkownika jest cicho resetowane do 0.33 przy `load_settings()` | ○ | ○ | ○ | ○ | **POTWIERDZONY — NISKI** (dodane przez konsolidatora) |
| — | „`code.strip()` usuwa spacje” | ○ | ○ | ⚠(KRYT) | ○ | **ODRZUCONY jako KRYTYCZNY → NISKI** (patrz §3) |
| — | Kod 200 znaków > MAX_PATH 260 | ○(OK) | ○(env) | ⚠(Ś) | ●(N) | **NIE REPRODUKUJE tutaj → NISKI, ryzyko zależne od środowiska** (patrz §3) |

¹ fable_4 zgłosił Ś5/N7 pod wspólną obserwacją „kwantyzacja przy niskim DPI” (B-12) — ten sam mechanizm.

---

## 2. Znaleziska wg wagi (z dowodem z ponownego uruchomienia)

### 🔴 KRYTYCZNY

**K1 — Excel: EAN-13 z wiodącym zerem, zapisany jako Liczba, cicho gubi zero i staje się Code128 ze ZŁĄ treścią, bez żadnego błędu.** *(wykrył TYLKO sonnet_2)*
- **Dowód (re-run konsolidatora):** poprawny EAN-13 `0501234123454` (suma zweryfikowana niezależnie) wpisany do komórki `.xlsx` jako liczba → `openpyxl` (read_only, data_only) oddaje `501234123454` (**12 cyfr, zero ucięte**) → `_detect_barcode_type` = `code128` → `generate()` **nie rzuca wyjątku**, tworzy kod Code 128; zxing potwierdza format `Code 128`, treść `501234123454`. Użytkownik zamówił EAN-13, dostał inny symbolizm z uciętą cyfrą — log pokazuje `[OK]`.
- **Dlaczego krytyczny:** to główna ścieżka produktu (import listy EAN z Excela). EAN-y z prefiksem 0 oraz UPC-A promowane do EAN-13 z wiodącym zerem są powszechne. Excel domyślnie traktuje wpis jako Liczbę i zawsze usuwa wiodące zera. Efekt: cicha korupcja danych na naklejkach, wykrywalna dopiero przy skanowaniu.
- **Poprawka (do decyzji):** w `_import_excel` czytać komórki jako tekst (nie `data_only` numerycznie) **lub** wykrywać 12-cyfrowe kody i ostrzegać/zero-padować („kod ma 12 cyfr — obcięty EAN-13?”). Docelowo: wspólna walidacja „to miał być EAN?” zamiast cichego fallbacku na Code128 (wspólny root-cause z N2).

### 🟠 ŚREDNI

**Ś1 — Maksymalne (każde z osobna dozwolone) wartości PARAM_RANGES dają obraz ~2,9 mld px → `PIL.DecompressionBombError`; komentarz w kodzie twierdzi, że temu zapobiega.** *(opus_1, sonnet_2, fable_4 — 3/4)*
- **Dowód:** `distance=10 × dpi=1200 × scale=3 × height=150` → obraz `2 887 680 066 px` → `DecompressionBombError: exceeds limit of 178956970`. Wysypują się też mniejsze kombinacje w zakresach (d=1/dpi=1200/sc=3/h=150 → 301 Mpx; d=10/dpi=1200/sc=3/h=9 → 185 Mpx). Komentarz `app.py:41` mówi wprost: *„Prevents … a multi-gigapixel image that hangs or crashes”* — **nieprawda**. Fable zmierzył ~118 s CPU przed krachem.
- **Skutek:** aplikacja nie ginie (łapane jako `except Exception` → `[ERR]`), ale komunikat jest surowy, po angielsku, o „decompression bomb DOS attack”; przy 100 kodach i braku przycisku anulowania to realne kilkuminutowe zawieszenie wątku. sonnet_2 zmierzył ~2,9 s/kod już przy `dpi=800, height=100, scale=2` (126 Mpx) — **wyraźnie poniżej maksimów**.
- **Poprawka:** wspólny limit powierzchni (`canvas_w*canvas_h ≤ ~100 Mpx`) sprawdzany w `generate()` PRZED renderem, rzucający czytelny `BarcodeError`; ewentualnie zacieśnić zakresy przy wysokim DPI. (Rozważyć przycisk anulowania w partii.)

**Ś2 — Nazwa urządzenia z rozszerzeniem (`con.x`, `nul.x`, `aux.data`, `com1.v2`) nie jest sanityzowana → surowy crash, żaden plik nie powstaje.** *(wykrył TYLKO fable_4)*
- **Dowód:** `safe_filename` sprawdza tylko DOKŁADNĄ nazwę (`stem.upper() in _WIN_RESERVED`), a Windows rezerwuje też nazwy, w których człon przed pierwszą kropką to urządzenie. Re-run: `con.x` → `UnsupportedOperation: File or stream is not seekable` (PIL pisze do konsoli urządzenia!), `nul.x` → `OSError [WinError 1]`, `aux.data`/`com1.v2` → `FileNotFoundError`. Użytkownik dostaje `[ERR]` z bezsensownym komunikatem.
- **Poprawka:** w `safe_filename` sprawdzać `stem.split(".")[0].upper() in _WIN_RESERVED`.

**Ś3 — Cyfry arabsko-indyjskie przechodzą jako EAN-13, a kod koduje INNE (ASCII) cyfry niż wpisano.** *(wykrył TYLKO fable_4)*
- **Dowód:** `"٥٩٠١٢٣٤١٢٣٤٥٧"` → `isdigit()`=True, `isascii()`=False, `_detect_barcode_type`=`ean13`; suma kontrolna liczy się poprawnie (`int()` rozumie te cyfry). Re-run: plik powstaje, zxing dekoduje **`5901234123457`** (ASCII) — czyli treść ≠ to, co użytkownik wpisał i co jest w nazwie pliku; aplikacja loguje `[OK]`. Niezgodność treści kodu z intencją.
- **Root-cause wspólny z N1:** `_detect_barcode_type` używa `.isdigit()` zamiast `.isascii() and .isdigit()`.
- **Poprawka:** wymagać ASCII w detekcji EAN — wtedy takie znaki trafią do Code128 i zostaną jawnie odrzucone jako >126.

**Ś4 — Strefa ciszy (quiet zone) przycięta do ~1 modułu; norma EAN-13 wymaga ≥11 modułów z lewej.** *(wykrył TYLKO fable_4)*
- **Dowód (pomiar z obrazu):** przy `distance=0.33 mm / dpi=300` lewy biały margines = **4 px = 1.0 moduł** (spec: 11). Generator renderuje 6.5 mm quiet zone, po czym kadruje do `side_pad = max(4, module_px)`. Czysty plik cyfrowy dekoduje się (zxing tolerancyjny), ale wydruk przycięty po krawędzi obrazka może nie być skanowalny czytnikami liniowymi.
- **Poprawka:** `side_pad ≥ 11 * module_px` dla EAN-13 (10 dla Code128), lub opcja w ustawieniach.

**Ś5 — „Szerokość modułu” nie ma efektu w paśmie 0.05–0.25 mm przy dpi=300 (martwa strefa).** *(sonnet_2 + fable_4)*
- **Dowód (re-run, hash SHA-256):** `distance` = 0.05 / 0.10 / 0.15 / 0.20 / 0.25 mm @ dpi=300 → **identyczny plik** (`344×175`, hash `4474da0af59e…`); dopiero 0.33 mm się różni (`388×175`). Podłoga 0.2 mm + kwantyzacja px zwija cały dolny fragment suwaka do jednego wyniku, choć `PARAM_RANGES` reklamuje 0.05 jako wartość użyteczną. To dokładnie klasa błędu, którą naprawiano jako BUG #2 („moduł nie działał”), tyle że na krańcu zakresu.
- **Poprawka:** podnieść dolną granicę `PARAM_RANGES["distance"]` do ~0.2 mm, albo pokazywać w UI efektywną szerokość modułu.

### 🟡 NISKI (skrót — pełne dowody w raportach cząstkowych)

- **N1** `²`/nieascii-cyfra → surowy `ValueError` w `_validate_ean13` (kontrakt API złamany; GUI ratuje szerokim `except`). *(fable_4)*
- **N2** `"…654.0"` → cicho Code128. **Łagodzące:** `openpyxl` oddaje int dla całkowitych liczb, więc realny import Excela jest bezpieczny; trigger wymaga literalnego `.0` (CSV/wklejka/tekst). *(opus_1 N, sonnet_2 K2, fable_4 Ś — rozbieżność wagi rozstrzygnięta na NISKI, §3)*
- **N3** `generate()` bez ochrony `height`/`scale`<0 → surowy `ValueError`; `height=0` → obraz bez pasków (zxing `None`) bez ostrzeżenia. GUI clampuje, ale to publiczne API (niespójne z guardem `dpi<=0`). *(opus_1, sonnet_2)*
- **N4** wszystkie `BarcodeError` po polsku → widoczne w logu `[ERR]` też w trybie EN. *(opus_1, sonnet_2, fable_4)*
- **N5** stopka copyright zaszyta po polsku poza `lang.py` (**konsensus 4/4**). 
- **N6** martwy kod `_count_data_modules` + `_PROBE_*`; nieużywany `import time` (dokładnie pułapka „wygląda na podpięte, nic nie robi” z briefu). *(opus_1, sonnet_2, fable_4)*
- **N7** martwa strefa `font_size` 0.5–2.2 mm @ dpi=72 (identyczny hash); przy domyślnym dpi=300 działa. *(sonnet_2, fable_4)*
- **N8** `scale="nan"` → 3.0 (NaN łamie `max/min`). Poprawka: `if math.isnan(val): raise`. *(fable_4)*
- **N9** przerwa po 7. znaku także dla Code128 ≥8 znaków — celowe wg komentarza, ale dla danych nie-EAN wygląda nieoczekiwanie. *(sonnet_2 obs., fable_4)*
- **N10** `_open_output_folder` po skasowaniu folderu → cichy no-op (brak `messagebox`). *(sonnet_2)*
- **N11** niespójność `grab_set()`: `_open_settings` woła natychmiast, `_open_help` odracza z komentarzem o tym samym race. *(fable_4)*
- **N12** pliki `*_backup_20260703.*` w repo, nie w `.gitignore`. *(sonnet_2)*
- **N13** `distance=0.15` wybrane świadomie przez użytkownika jest przy następnym `load_settings()` cicho resetowane do 0.33 — migracja nie odróżnia legacy-martwego 0.15 od wyboru użytkownika. **Dowód (re-run):** zapis 0.15 (w zakresie 0.05–10) → odczyt 0.33. *(dodane przez konsolidatora — żaden agent tego nie flagował; wszyscy testowali migrację jako „poprawną”)*

---

## 3. Rozstrzygnięcia rozbieżności (odtworzone ręcznie, nie głosowaniem)

**(a) haiku_3: „`code.strip()` usuwa spacje” = KRYTYCZNY → ODRZUCONO / obniżono do NISKI.**
haiku scharakteryzował to jako „obcina WSZYSTKIE spacje, w tym w środku”. **Re-run obala:** spacje **w środku** kodu są zachowane i dekodują się 1:1 (`'AB  CD'` → zxing czyta `'AB  CD'`; `'A B'` → `'A B'`) — czyli wymaganie fazy 4 „same spacje w środku” DZIAŁA. `.strip()` usuwa jedynie spacje wiodące/końcowe (obronna higiena wejścia) i odrzuca kod złożony z samych spacji (`'   '` → „Pusty kod”, obronne). To NIE jest krytyczne; co najwyżej NISKA obserwacja (ciche przycięcie spacji brzegowych). opus_1 i fable_4 jawnie testowały spacje wewnętrzne i potwierdziły działanie — haiku miał tu ślepą plamkę i zawyżoną wagę. **Wniosek: pojedynczy „krytyk” wymaga weryfikacji — tu weryfikacja go obaliła.**

**(b) Waga N2 (`.0` → Code128): K2/KRYT (sonnet) vs Ś (fable) vs NISKI (opus).**
Rozstrzygnięcie na **NISKI**: główna ścieżka importu jest bezpieczna, bo `openpyxl` zwraca `int` dla liczb całkowitych (re-run: komórka `5907925017654.0` → `"5907925017654"`, poprawny EAN-13). Trigger wymaga literalnego stringa `".0"` (CSV, wklejka, komórka tekstowa). Realny, ale wąski. Dzieli root-cause z K1 (brak walidacji „to miał być EAN”), więc naprawiać razem.

**(c) MAX_PATH 260: haiku „FAIL/Ś” vs opus „OK” vs sonnet/fable „env-dependent”.**
Rozstrzygnięcie: **NIE reprodukuje na tej maszynie.** Re-run: kod 200 znaków w katalogu dającym ścieżkę 250–387 znaków → plik powstaje (long paths włączone + manifest Pythona 3.14). haiku raportował twardy FAIL, którego nie da się tu odtworzyć — jego test w finalnym pliku i tak asertuje zachowanie zależne od środowiska (suita zielona). **Realne ryzyko** pozostaje na domyślnym Win10 (`LongPathsEnabled=0`) i w `BarcodeGen.exe` z PyInstaller (manifest może nie mieć `longPathAware`) → waga **NISKI**, zależne od środowiska. Poprawka defensywna: limit długości kodu lub prefiks `\\?\`.

**(d) Rozjazd testu deterministycznego = sygnał alarmowy?** Nie stwierdzono. Poza (a) (błąd testera, nie apki) wszystkie modele zgodnie odtworzyły fazy 1–4 (najwęższy pasek == wzór, czcionka 35 px co do piksela w 5 konfiguracjach, migracje rejestru, przerwa 67 px po 7. znaku, partia 8/10). Aplikacja jest deterministyczna — rozbieżności brały się z RÓŻNEJ GŁĘBI polowania (faza 5), nie z niestabilności.

---

## 4. Statystyki per model i wartość multi-model

| Model | Testy | Znaleziska (K/Ś/N) | Unikatowe realne | Fazy unikatów | Ocena |
|---|:--:|:--:|---|---|---|
| **opus_1** | 46 | 0 / 1 / 6 | brak własnych unikatów; najsolidniejszy na bombie + walidacji API | — | Rzetelny, potwierdzający |
| **sonnet_2** | 54 | 3 / 5 / 5 | **K1 (leading-zero EAN — jedyny prawdziwy KRYT)**, N10, N12; realne headless-GUI (CTk) | 3 (Excel), 4b | Najszerszy zasięg; złapał jedyny krytyk |
| **haiku_3** | 26 | 1 / 2 / 0 | brak (KRYT=fałszywy, footer=konsensus, MAX_PATH=env) | — | Najsłabszy; wygenerował fałszywy krytyk |
| **fable_4** | 30 | 1 / 5 / 7 | **Ś2 device+ext, Ś3 arabskie cyfry, Ś4 quiet zone, N1 `²`, N8 nan, N11 grab_set** | 5 (polowanie), 1 | Najbogatsze polowanie swobodne |

**Werdykt: multi-model miał tu REALNĄ wartość.** Najgroźniejsze znalezisko (K1) wykrył **tylko** sonnet_2; najbogatszy zbiór unikatowych, potwierdzonych bugów (device+ext, arabskie cyfry, quiet zone) — **tylko** fable_4. Żaden pojedynczy przebieg nie znalazł wszystkiego; pojedynczy run pominąłby albo K1, albo klaster fable. Fazy 1–4 (deterministyczne) były niemal identyczne u wszystkich — potwierdziły stabilność, ale nie dały nowych bugów. **Cała wartość różnicowa powstała w Fazie 5 (polowanie swobodne)** — dokładnie jak przewidywał brief. Dodatkowo haiku pokazał ryzyko odwrotne: słabszy model wyprodukował fałszywy „krytyk”, który dopiero ponowna weryfikacja obaliła — argument za konsolidacją z re-runem zamiast głosowania.

---

## 5. Checklist wymagań klienta (pkt 27) — skonsolidowany

| Wymaganie | Werdykt (4/4 modele) | Dowód (pomiarowy) | Zastrzeżenie |
|---|:--:|---|---|
| Moduł steruje szerokością kodu | ✅ SPEŁNIONE | najwęższy pasek px == `max(2, round(max(0.05,d)·scale·dpi/25.4))` z podłogą 0.2 mm; potwierdzone dla ~40–62 kombinacji/model, 0 rozjazdów | martwa strefa 0.05–0.25 mm @ dpi=300 (**Ś5**) |
| Czcionka absolutna (niezależna od wymiarów) | ✅ SPEŁNIONE | font_size=3 mm, 5 konfiguracji (height 1→150, distance, scale) → **35 px co do piksela** we wszystkich (pomiar z obrazu, nie metadanych) | — |
| Czcionka bez sufitu (rośnie liniowo) | ✅ SPEŁNIONE | font_size=15 mm @ height=150 generuje i dekoduje; target = `round(fs·dpi/25.4)` rośnie liniowo (142 px @1200 dpi) | — |
| Skala tekstu w mm | ✅ SPEŁNIONE | 3.0 mm → zmierzone 2.96–3.17 mm @ 72/300/1200 dpi; migracja legacy 12→20.3→clamp 15.0 działa | martwa strefa 0.5–2.2 mm @ dpi=72 (**N7**) |
| Tracking + przerwa po 7. znaku | ✅ SPEŁNIONE | pomiar kolumn glifów EAN-13: przerwy `[5,7,9,11,7,6,`**`67`**`,12,6,6,6,5]` px — po 7. znaku 67 px (>3× tracking); Code128 <7 znaków nie psuje układu | gap też na Code128 ≥8 znaków (**N9**, celowe) |
| DPI wspólne, 300 działa | ✅ SPEŁNIONE | cała macierz @ dpi=300 dekoduje 1:1; PNG zapisany z `dpi=(300,300)` | — |

---

## 6. Rzeczy niesprawdzalne automatycznie (zgodnie u wszystkich modeli)

Czysto interaktywne kroki GUI (okna dialogowe kolizji/duplikatów/nadpisania, wizualny render motywu jasny/ciemny, `os.startfile` otwierające Explorera, fizyczny drag suwaka, zamknięcie procesu w trakcie generacji) — testowano **logikę** stojącą za nimi (walidacja zakresów, wykrywanie duplikatów/kolizji, parsowanie skali, zachowanie stanu przy `_rebuild_ui`, reuse okna pomocy przez `winfo_exists`), a interakcję oznaczono jako manualną. sonnet_2 dodatkowo uruchomił **realne, niewidoczne widżety CTk bez `mainloop()`** i potwierdził część z nich na żywo (walidacja dpi=10000 nie zapisuje wartości; „Przywróć domyślne” resetuje; zmiana języka zachowuje kody/log/progress; reuse okna pomocy — `winfo_id` identyczny). Zamknięcie w trakcie generacji: wątek `daemon=True` ginie z procesem; **brak przycisku anulowania — ODNOTOWANE** (istotne w połączeniu z Ś1: generacje ~min bez możliwości przerwania).

---

## 7. Rekomendowane poprawki (pogrupowane; NIE wdrożone — do osobnej decyzji)

1. **Walidacja „to miał być EAN” (naprawia K1 + N2):** czytać Excel jako tekst lub ostrzegać/zero-padować 12-cyfrowe kody; normalizować `^\d{13}\.0$`. **Priorytet 1.**
2. **Wspólny limit powierzchni obrazu w `generate()` (naprawia Ś1):** `canvas_w*canvas_h ≤ ~100 Mpx` → czytelny `BarcodeError` przed renderem; rozważyć przycisk anulowania partii.
3. **`safe_filename`: `stem.split(".")[0].upper() in _WIN_RESERVED` (naprawia Ś2).**
4. **Detekcja EAN wymaga ASCII: `code.isascii() and code.isdigit()` (naprawia Ś3 + N1).**
5. **`side_pad ≥ 11·module_px` dla EAN-13 (naprawia Ś4).**
6. **Podnieść `PARAM_RANGES["distance"]` do ~0.2 mm lub pokazywać efektywny moduł (naprawia Ś5); analogicznie podłoga font_size vs dpi (N7).**
7. **Guard `height>0`/`scale>0` w `generate()` + `math.isnan` (naprawia N3 + N8).**
8. **i18n:** przenieść komunikaty `BarcodeError` i stopkę do `lang.py` (N4, N5).
9. **Sprzątanie:** usunąć `_count_data_modules`/`_PROBE_*`/`import time` (N6), pliki `*_backup_*` do `.gitignore` (N12).
10. **N13:** rozważyć porzucenie heurystyki resetu 0.15 (lub oprzeć migrację na jawnym znaczniku wersji, nie na wartości).

---

## 8. Załączniki (raporty i testy cząstkowe)

| Model | Raport | Testy | Wynik pytest |
|---|---|---|---|
| opus_1 | `QA_RAPORT_opus_1.md` | `tests/test_qa_audit_opus_1.py` | 46 passed |
| sonnet_2 | `QA_RAPORT_sonnet_2.md` | `tests/test_qa_audit_sonnet_2.py` | 54 passed |
| haiku_3 | `QA_RAPORT_haiku_3.md` | `tests/test_qa_audit_haiku_3.py` | 25 passed, 1 skipped |
| fable_4 | `QA_RAPORT_fable_4.md` | `tests/test_qa_audit_fable_4.py` | 30 passed |
| **Suma** | **QA_RAPORT_FINALNY.md** (ten plik) | **`pytest tests/`** | **163 passed, 1 skipped** |

Wspólny prompt audytu: `AUDIT_INSTRUKCJE_SHARED.md`. Rejestr: wszystkie podklucze `Software\BarcodeGen_QA_*` usunięte; prawdziwy `Software\BarcodeGen` nietknięty.
