"""
UI strings for PL / EN
"""

LANG = {
    "PL": {
        "settings":         "Ustawienia",
        "input_label":      "Kody do wygenerowania (każdy w osobnej linii, max 100):",
        "import_excel":     "Importuj z Excela (.xlsx)",
        "clear":            "Wyczyść",
        "generate":         "Generuj kody",
        "open_folder":      "Otwórz folder wyników",
        "log_label":        "Log / wyniki:",
        "output_dir":       "Folder wyjściowy:",
        "param_height":     "Wysokość kodu:",
        "param_distance":   "Dystans (mm):",
        "param_font_size":  "Rozmiar tekstu:",
        "param_dpi":        "DPI:",
        "save":             "Zapisz",
        "no_codes":         "Brak kodów do wygenerowania.",
        "too_many":         "Maksymalnie 100 kodów na raz. Wpisałeś: {n}.",
        "done":             "Zakończono generowanie.",
        "result_count":     "Wygenerowano: {ok}/{total}",
        "errors_summary":   "Błędy ({n}):",
        "excel_loaded":     "Wczytano {n} kodów z pliku: {file}",
        "excel_error":      "Błąd odczytu pliku Excel:",
        "invalid_params":   "Nieprawidłowe wartości parametrów. Sprawdź wpisy.",
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
        "input_label":      "Codes to generate (one per line, max 100):",
        "import_excel":     "Import from Excel (.xlsx)",
        "clear":            "Clear",
        "generate":         "Generate barcodes",
        "open_folder":      "Open output folder",
        "log_label":        "Log / results:",
        "output_dir":       "Output folder:",
        "param_height":     "Barcode height:",
        "param_distance":   "Distance (mm):",
        "param_font_size":  "Font size:",
        "param_dpi":        "DPI:",
        "save":             "Save",
        "no_codes":         "No codes to generate.",
        "too_many":         "Maximum 100 codes at once. You entered: {n}.",
        "done":             "Generation complete.",
        "result_count":     "Generated: {ok}/{total}",
        "errors_summary":   "Errors ({n}):",
        "excel_loaded":     "Loaded {n} codes from file: {file}",
        "excel_error":      "Error reading Excel file:",
        "invalid_params":   "Invalid parameter values. Please check your input.",
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
