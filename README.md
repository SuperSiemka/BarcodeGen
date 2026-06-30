# BarcodeGen

Desktopowa aplikacja do generowania kodów kreskowych EAN-13 i Code128.

Zbudowana w Pythonie (CustomTkinter + Pillow + python-barcode).

---

## Wymagania

- Python 3.10 lub nowszy
- Windows 10 / 11

---

## Uruchomienie na nowym komputerze

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/SuperSiemka/BarcodeGen.git
cd BarcodeGen
```

### 2. (Opcjonalnie) Utwórz wirtualne środowisko

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 4. Uruchom aplikację

```bash
python app.py
```

---

## Budowanie pliku .exe

Uruchom skrypt:

```bash
build.bat
```

Gotowy plik `BarcodeGen.exe` pojawi się w folderze `dist\`.

---

## Struktura projektu

```
BarcodeGen/
├── app.py            # Główna aplikacja GUI
├── generator.py      # Logika generowania kodów kreskowych
├── lang.py           # Tłumaczenia PL / EN
├── build.bat         # Skrypt budujący plik .exe (PyInstaller)
├── requirements.txt  # Zależności Python
├── icon.ico / icon.png
└── logo.ico / logo.png
```

---

## Ustawienia

Ustawienia aplikacji (folder wyjściowy, DPI, skala itp.) są zapisywane w rejestrze Windows:

```
HKEY_CURRENT_USER\Software\BarcodeGen
```

---

© 2026 [dCoded](https://www.dcoded.pl) & [id3ntity](https://www.id3ntity.pl)
