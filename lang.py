"""
UI strings for PL / EN
"""

LANG = {
    "PL": {
        "settings":         "Ustawienia",
        "help":             "Instrukcja",
        "help_title":       "Instrukcja obsługi",
        "help_close":       "Zamknij",
        "help_body": (
            "BarcodeGen — generator kodów kreskowych (EAN-13 / Code128)\n"
            "══════════════════════════════════════════════════════════\n"
            "\n"
            "1. WPISYWANIE KODÓW\n"
            "   • Wpisz kody w pole tekstowe — każdy w osobnej linii (max 100).\n"
            "   • 13 cyfr = EAN-13 (sprawdzana suma kontrolna). Cokolwiek innego\n"
            "     = Code128 (litery, cyfry, myślniki itp.).\n"
            "   • Uwaga: kod 12-cyfrowy zostanie wygenerowany jako Code128, a nie\n"
            "     jako EAN/UPC. Do EAN-13 podaj pełne 13 cyfr.\n"
            "\n"
            "2. IMPORT Z EXCELA\n"
            "   • Przycisk „Importuj z Excela (.xlsx)”. Kody muszą być w pierwszej\n"
            "     kolumnie (A) pierwszego arkusza, bez nagłówka. Tylko pliki .xlsx.\n"
            "\n"
            "3. ROZMIAR I WYGLĄD KODU\n"
            "   • Suwak „Rozmiar kodu” — ogólne powiększenie: skaluje szerokość\n"
            "     kresek ORAZ wysokość kodu. NIE zmienia rozmiaru cyfr pod kodem.\n"
            "   • Ustawienia (przycisk „Ustawienia”) zawierają:\n"
            "       – Wysokość kodu (mm) — wysokość samych kresek.\n"
            "       – Szerokość modułu (mm) — szerokość najcieńszej kreski; to ONA\n"
            "         decyduje o końcowej szerokości kodu (0.33 mm = nominał EAN).\n"
            "       – Skala tekstu — rozmiar cyfr pod kodem. Jest NIEZALEŻNY od\n"
            "         wysokości/szerokości kodu i rośnie liniowo bez ograniczenia.\n"
            "       – DPI — rozdzielczość (domyślnie 300; punktów na cal).\n"
            "\n"
            "4. FOLDER WYJŚCIOWY\n"
            "   • W „Ustawieniach” ustaw folder zapisu. Puste = podfolder „output”\n"
            "     obok programu. Każdy kod zapisywany jest jako PLIK PNG.\n"
            "\n"
            "5. GENEROWANIE\n"
            "   • „Generuj kody” tworzy pliki PNG. Pasek postępu i log pokazują\n"
            "     wynik ([OK]/[ERR]). „Otwórz folder wyników” otwiera katalog.\n"
            "   • Duplikaty i istniejące pliki — program zapyta, zanim nadpisze.\n"
            "\n"
            "6. JĘZYK / MOTYW\n"
            "   • Przyciski w prawym górnym rogu: język PL/EN, jasny/ciemny motyw.\n"
            "     Zmiana języka zachowuje wpisane kody.\n"
        ),
        "input_label":      "Kody do wygenerowania (każdy w osobnej linii, max 100):",
        "import_excel":     "Importuj z Excela (.xlsx)",
        "clear":            "Wyczyść",
        "generate":         "Generuj kody",
        "open_folder":      "Otwórz folder wyników",
        "log_label":        "Log / wyniki:",
        "output_dir":       "Folder wyjściowy:",
        "param_height":     "Wysokość kodu (mm):",
        "param_distance":   "Szerokość modułu (mm):",
        "param_font_size":  "Skala tekstu:",
        "param_dpi":        "DPI:",
        "scale_label":      "Rozmiar kodu:",
        "scale_unit":       "×",
        "save":             "Zapisz",
        "no_codes":         "Brak kodów do wygenerowania.",
        "too_many":         "Maksymalnie 100 kodów na raz. Wpisałeś: {n}.",
        "done":             "Zakończono generowanie.",
        "result_count":     "Wygenerowano: {ok}/{total}",
        "errors_summary":   "Błędy ({n}):",
        "excel_loaded":     "Wczytano {n} kodów z pliku: {file}",
        "excel_error":      "Błąd odczytu pliku Excel:",
        "invalid_params":   "Nieprawidłowe wartości parametrów. Sprawdź wpisy.",
        "output_dir_error": "Nie można użyć folderu wyjściowego:",
        "duplicates_found": (
            "Wykryto duplikaty: {codes}.\n"
            "Czy chcesz pominąć duplikaty i kontynuować?"
        ),
        "files_exist": (
            "{n} plik(ów) już istnieje (np. {examples}).\n"
            "Czy nadpisać istniejące pliki?"
        ),
        "excel_hint": (
            "Wskazówka: plik Excel powinien zawierać kody w pierwszej kolumnie "
            "(A) pierwszego arkusza, bez nagłówka."
        ),
    },
    "EN": {
        "settings":         "Settings",
        "help":             "Manual",
        "help_title":       "User manual",
        "help_close":       "Close",
        "help_body": (
            "BarcodeGen — barcode generator (EAN-13 / Code128)\n"
            "══════════════════════════════════════════════════\n"
            "\n"
            "1. ENTERING CODES\n"
            "   • Type codes into the text box — one per line (max 100).\n"
            "   • 13 digits = EAN-13 (checksum validated). Anything else =\n"
            "     Code128 (letters, digits, dashes, etc.).\n"
            "   • Note: a 12-digit code is generated as Code128, NOT as an\n"
            "     EAN/UPC barcode. For EAN-13 enter the full 13 digits.\n"
            "\n"
            "2. IMPORT FROM EXCEL\n"
            "   • “Import from Excel (.xlsx)”. Codes must be in the first column\n"
            "     (A) of the first sheet, with no header row. Only .xlsx files.\n"
            "\n"
            "3. BARCODE SIZE & LOOK\n"
            "   • “Barcode size” slider — overall zoom: scales bar width AND\n"
            "     bar height. It does NOT change the size of the digits below.\n"
            "   • Settings (the “Settings” button) contain:\n"
            "       – Bar height (mm) — height of the bars only.\n"
            "       – Module width (mm) — width of the thinnest bar; THIS drives\n"
            "         the final barcode width (0.33 mm = EAN nominal).\n"
            "       – Text scale — size of the digits below the code. INDEPENDENT\n"
            "         of the code’s height/width, grows linearly with no cap.\n"
            "       – DPI — resolution (default 300; dots per inch).\n"
            "\n"
            "4. OUTPUT FOLDER\n"
            "   • Set the save folder in “Settings”. Empty = an “output” subfolder\n"
            "     next to the program. Each code is saved as a PNG FILE.\n"
            "\n"
            "5. GENERATING\n"
            "   • “Generate barcodes” creates the PNG files. The progress bar and\n"
            "     log show the result ([OK]/[ERR]). “Open output folder” opens it.\n"
            "   • Duplicates and existing files — you are asked before overwriting.\n"
            "\n"
            "6. LANGUAGE / THEME\n"
            "   • Buttons in the top-right corner: PL/EN language, light/dark theme.\n"
            "     Switching language keeps the codes you already typed.\n"
        ),
        "input_label":      "Codes to generate (one per line, max 100):",
        "import_excel":     "Import from Excel (.xlsx)",
        "clear":            "Clear",
        "generate":         "Generate barcodes",
        "open_folder":      "Open output folder",
        "log_label":        "Log / results:",
        "output_dir":       "Output folder:",
        "param_height":     "Bar height (mm):",
        "param_distance":   "Module width (mm):",
        "param_font_size":  "Text scale:",
        "param_dpi":        "DPI:",
        "scale_label":      "Barcode size:",
        "scale_unit":       "×",
        "save":             "Save",
        "no_codes":         "No codes to generate.",
        "too_many":         "Maximum 100 codes at once. You entered: {n}.",
        "done":             "Generation complete.",
        "result_count":     "Generated: {ok}/{total}",
        "errors_summary":   "Errors ({n}):",
        "excel_loaded":     "Loaded {n} codes from file: {file}",
        "excel_error":      "Error reading Excel file:",
        "invalid_params":   "Invalid parameter values. Please check your input.",
        "output_dir_error": "Cannot use the output folder:",
        "duplicates_found": (
            "Duplicates detected: {codes}.\n"
            "Skip duplicates and continue?"
        ),
        "files_exist": (
            "{n} file(s) already exist (e.g. {examples}).\n"
            "Overwrite existing files?"
        ),
        "excel_hint": (
            "Hint: the Excel file should contain codes in the first column (A) "
            "of the first sheet, with no header row."
        ),
    },
}
