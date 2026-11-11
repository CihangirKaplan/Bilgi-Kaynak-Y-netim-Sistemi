@echo off
rem TKYS - Yonetici (ADMIN) parola kurtarma. Yalnizca SUNUCU bilgisayarinda calistirin.
chcp 65001 >nul
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\admin_parola_kurtar.py
) else (
    python scripts\admin_parola_kurtar.py
)
echo.
pause
