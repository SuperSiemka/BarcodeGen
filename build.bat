@echo off
REM Build BarcodeGen into a single .exe (no installer needed)

echo [BarcodeGen] Installing dependencies...
pip install -r requirements.txt

echo [BarcodeGen] Building executable...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name BarcodeGen ^
    --icon logo.ico ^
    --add-data "lang.py;." ^
    --add-data "logo.png;." ^
    --add-data "logo.ico;." ^
    --add-data "icon.ico;." ^
    --add-data "icon.png;." ^
    app.py

echo [BarcodeGen] Done! Executable is in dist\BarcodeGen.exe
pause
