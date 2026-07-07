# WSPÓLNE INSTRUKCJE AUDYTU QA — BarcodeGen v1.0.1 (commit e6fcdd9)

Jesteś **wrogim testerem QA**. Twoim zadaniem NIE jest potwierdzić, że apka działa —
jest ZNALEŹĆ błędy. Płacą Ci od znalezionego buga.

## ŻELAZNE ZASADY (dowód, nie opinia)
- Każdy wniosek MUSI mieć DOWÓD z **uruchomionego kodu**: hash pliku, wymiar obrazu,
  wynik dekodera zxing, treść wyjątku, zmierzona liczba pikseli. Zdanie „sprawdziłem,
  działa" bez dowodu obok = niedopuszczalne.
- Czytanie kodu to HIPOTEZA, nie werdykt. Werdyktem jest URUCHOMIENIE. W tym repo był
  parametr, który „wyglądał na podpięty", a przez wiele wersji nic nie robił — wykryto to
  dopiero porównaniem hashy plików. Bądź tak samo podejrzliwy.
- **NIE modyfikuj** `app.py`, `generator.py`, `lang.py` ani `tests/test_scaling.py`.
- Nowe testy pisz WYŁĄCZNIE do swojego pliku (patrz sekcja Izolacja).
- NIE wdrażaj poprawek do kodu aplikacji. Błędy zgłoś z PROPOZYCJĄ poprawki w raporcie.

## Środowisko (już przygotowane)
- Python 3.14, katalog roboczy: `c:\Users\Super\projekty\BarcodeGen`
- Zainstalowane: `pytest`, `zxing-cpp` (import: `import zxingcpp`; dekodowanie:
  `zxingcpp.read_barcodes(PIL_Image)` → lista, `.text` = odczytany kod), `openpyxl`,
  `pillow` (PIL), `python-barcode`.
- Import logiki: `from generator import BarcodeGenerator, BarcodeError, safe_filename, _ean13_checksum, _detect_barcode_type` itd. `from app import load_settings, save_settings, DEFAULT_SETTINGS, PARAM_RANGES` (uwaga: `app` importuje customtkinter — jeśli import się wysypie w headless, zaraportuj to jako fakt i testuj logikę przez kopię funkcji lub importuj ostrożnie).

## FAZA 1 — poprawność generowania (dowody: hashe, wymiary, dekodowanie)
1. **Macierz parametrów** — próbkuj ~40 kombinacji z:
   `distance {0.05, 0.2, 0.33, 1, 5, 10}` × `font_size {0.5, 2.2, 8, 15}` ×
   `height {1, 9, 150}` × `dpi {72, 300, 1200}` × `scale {0.5, 1, 3}`,
   uwzględnij WSZYSTKIE skrajne. Dla KAŻDEJ:
   (a) plik powstał; (b) zxing dekoduje **dokładnie** wejściowy kod;
   (c) hash pliku różny od pozostałych kombinacji;
   (d) najwęższy pasek w px == `max(2, round(max(0.05,distance)*scale*dpi/25.4))`
   z poprawką na podłogę 0.2 mm. **NIE** testuj proporcji szerokości wprost —
   kwantyzacja do pełnych px daje np. 2.125 zamiast 2.0 i to jest POPRAWNE.
   Użyj EAN-13 poprawnego (np. `5901234123457`) i osobno Code128 (np. `ABC-123`).
2. **Czcionka absolutna**: `font_size=3` przy 5 różnych konfiguracjach (height, distance,
   dpi, scale) → wysokość glifów w px IDENTYCZNA co do piksela (zmierz z OBRAZU, nie
   metadanych). Na Windows dodatkowo: zmierzona wysokość ≈ `font_size*dpi/25.4 ± 2 px`
   (kalibracja mm, Arial). UWAGA: przy stałym font_size ale RÓŻNYM dpi wysokość w px
   zależy od dpi — trzymaj dpi stałe dla testu „identyczne co do piksela", a zależność mm
   testuj osobno przy dpi=300.
3. **EAN-13**: 20 losowych poprawnych kodów (sumę kontrolną wylicz NIEZALEŻNĄ własną
   implementacją) → wszystkie dekodują się. 20 z celowo zepsutą sumą → wszystkie rzucają
   `BarcodeError` wskazujący właściwą oczekiwaną cyfrę.
4. **Code128**: znaki graniczne ASCII 32 (spacja) i 126 (`~`) dozwolone; 31 i 127
   odrzucone; kod 1-znakowy; kod 80-znakowy; same spacje w środku. Sprawdź czy dozwolone
   faktycznie DEKODUJĄ się poprawnie.

## FAZA 2 — pliki i system (Windows, NTFS)
5. Kody `CON, PRN, NUL, com5, lpt9` → pliki `_CON.png` itd. muszą FIZYCZNIE powstać
   (`exists()` + rozmiar>0). Sprawdź dokładną nazwę z `safe_filename`.
6. `AB/CD` vs `AB?CD` → potwierdź że `safe_filename` daje KOLIZJĘ (ta sama nazwa), i że
   logika w `app._on_generate` wykrywa ją PRZED generowaniem (przetestuj samą logikę
   kolizji, nie GUI).
7. Nadpisanie: wygeneruj kod 2× → `mtime` pliku się zaktualizował (użyj `os.stat().st_mtime_ns`,
   ewentualnie odczekaj/wymuś, żeby rozdzielczość zegara nie zamaskowała zmiany).
8. Kod 200 znaków → czy nazwa/ścieżka pliku nie przekracza limitu Windows (260)? Jeśli
   przekracza i generacja się wysypuje — to BUG, zgłoś z dowodem (treść wyjątku).

## FAZA 3 — ustawienia i rejestr
9. **Izoluj rejestr** (patrz sekcja Izolacja — użyj własnego podklucza!). Zapisz kolejno i
   po KAŻDYM uruchom `load_settings()`, udowodnij brak wyjątku i poprawną wartość:
   - `language="DE"` → po walidacji `"PL"` (DE nie ma w LANG)
   - `theme="neon"` → `"dark"`
   - `dpi="99999"` → clamp do `1200`
   - `font_size="12"` BEZ `font_unit` → migracja `12*1.693=20.316→round 20.3→clamp 15.0`
   - `distance="0.15"` → migracja do `0.33` (default)
   Kolejność migracji/clamp ma znaczenie — sprawdź wynik końcowy. Przywróć rejestr po testach.
10. **Excel**: zbuduj `.xlsx` z komórkami w kolumnie A: int, float z `.0`, tekst, formuła
    (czytana `data_only`), pusta, data (datetime), 500 wierszy → odwzoruj logikę importu z
    `app._import_excel` (iter_rows min_row=1, values_only, `str(row[0]).strip()`, pomiń None/puste)
    i sprawdź że wynik = oczekiwana lista. Dodatkowo: kod EAN z kropką `"5907925017654.0"`
    (tak float trafia z Excela) → co robi generator? Oceń, czy to sensowne (13 cyfr vs string
    z kropką → Code128? błąd sumy? zła długość?). To potencjalny BUG — zbadaj.

## FAZA 4 — GUI (jeśli automat nie sięga, oznacz „niesprawdzalne automatycznie" z uzasadnieniem)
Nie uruchamiaj pełnego `mainloop()`. Interaktywne kroki (11–16, 24–26) oznacz jako manualne,
ale WSZĘDZIE gdzie da się wyekstrahować logikę — testuj logikę:
- 11. dpi=10000 w `_open_settings._save` → walidacja `PARAM_RANGES` odrzuca (logika: czy
  `not (72 <= 10000 <= 1200)` → ValueError → messagebox, wartość NIE zapisana). Sprawdź logikę.
- 12/20. `AB/CD` i `AB?CD` → okno kolizji; `AB/CD`×3 duplikat. Testuj logikę wykrywania.
- 13. Przełączenie języka zachowuje wpisane kody (logika `_rebuild_ui`). Szukaj „sierot"
  językowych: stringi w kodzie POZA `lang.py` (np. „Wszelkie prawa zastrzeżone", `[OK]`,
  `[ERR]`, tytuł, komunikaty) — wypisz każdy nieprzetłumaczalny string.
- 14. „Przywróć domyślne" → `DEFAULT_SETTINGS` + zapis. Sprawdź logikę `_reset_defaults`.
- 15/16. Generacja w wątku daemon; brak przycisku anulowania → ODNOTUJ. Zamknięcie w trakcie
  → wątek daemon ginie z procesem (oceń z kodu, oznacz jako manualne jeśli trzeba).

## FAZA 4b — funkcje pominięte + wymagania klienta (commit 8fbd75c „Text spacing")
19. **ODSTĘPY TEKSTU**: na wygenerowanym obrazie ZMIERZ w pikselach odstępy między glifami.
    Musi być wyraźnie większa przerwa PO 7. znaku (`_GAP_RATIO=2.2` szer. cyfry) oraz
    jednolity tracking (`_TRACKING_RATIO=0.10`) między pozostałymi. Zweryfikuj POMIAREM
    (znajdź kolumny glifów, policz odstępy) dla EAN-13 i dla Code128 <7 znaków (czy brak
    7. znaku nie psuje układu?).
20. **Duplikaty KODÓW** (nie mylić z kolizją nazw): ten sam kod 3× → logika `_on_generate`
    wykrywa duplikat, pyta, po „Tak" filtruje do `unique`. Sprawdź też duplikat z Excela.
21. **Partia z błędem w środku**: 10 kodów, 2 z błędną sumą → 8 plików powstaje, podsumowanie
    wymienia dokładnie 2 błędne z powodami, pasek postępu dochodzi do końca. Odwzoruj pętlę
    `worker()` (bez GUI) i sprawdź.
22. **Katalog wyjściowy**: (a) pusty w ustawieniach → `app_dir()/output` (gdzie dokładnie?);
    (b) ścieżka nieistniejąca → `_resolve_output_dir` robi `mkdir(parents=True)`; (c) ścieżka
    bez prawa zapisu → czytelny błąd (OSError łapany), nie crash. Sprawdź logikę.
23. „Otwórz folder": `_open_output_folder` używa `os.startfile`; zachowanie gdy folder skasowano
    (sprawdza `.exists()`). Oceń z kodu.
24. Suwak „Rozmiar kodu": wpisz `"1,5"` (przecinek), `"abc"`, `"0.1"`, `"99"` → `_on_scale_entry`
    parsuje (`.replace(",",".")`), clamp 0.5–3.0. Sprawdź logikę parsowania/clampu.
25. Motyw dark↔light: `_toggle_theme` zapis w rejestrze. (GUI: manualne.)
26. Okno pomocy: `_open_help` reuse istniejącego okna (podwójne kliknięcie nie tworzy 2. okna).
    Oceń logikę `_help_win` + `winfo_exists`.
27. **Checklist wymagań klienta** — w raporcie OSOBNA tabela z kolumnami i linkiem do dowodu:
    `[moduł steruje szerokością] [czcionka absolutna] [czcionka bez sufitu] [skala tekstu w mm]
    [tracking + przerwa po 7. znaku] [dpi wspólne 300 działa]`.

## FAZA 5 — polowanie swobodne (NAJCENNIEJSZE — min. realny wysiłek)
17. Przeczytaj CAŁY `app.py` i `generator.py` szukając: parametrów nieużywanych w ciele
    funkcji, wartości liczonych i porzucanych, warunków zawsze prawda/fałsz, rozjazdów
    kod↔docstring, stringów poza `lang.py`, wycieków uchwytów okien. KAŻDĄ hipotezę POTWIERDŹ
    lub OBAL uruchomieniem.
18. Wymyśl **5 własnych** scenariuszy ataku spoza tej listy i wykonaj je (np. kod z białymi
    znakami w środku, Unicode/emoji, ujemne/olbrzymie wartości, `distance` bardzo małe vs
    podłoga 0.2 mm, EAN z wiodącymi zerami, bardzo długi Code128 vs pamięć, itp.).

## RAPORT — struktura pliku QA_RAPORT_<TAG>.md
Sekcje: **Środowisko** • **Wykonane testy + dowody** (tabela: test → dowód/liczba/hash) •
**Znalezione błędy** (waga: KRYTYCZNY / ŚREDNI / NISKI, każdy z: opis, dowód z uruchomienia,
proponowana poprawka) • **Tabela checklist wymagań klienta (pkt 27)** • **Niesprawdzalne
automatycznie** (co i dlaczego).

## NA KONIEC
`pytest tests/test_qa_audit_<TAG>.py -v` musi przejść (Twoje testy zielone; jeśli test
udowadnia buga, niech asertuje AKTUALNE błędne zachowanie i opisz to jako bug w raporcie —
NIE zostawiaj czerwonego testu bez wyjaśnienia). Zwróć w finalnej wiadomości: liczbę
znalezisk wg wagi, listę unikatowych/najciekawszych znalezisk, i których faz dotyczyły.
