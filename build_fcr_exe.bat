@echo off
chcp 65001 >nul
title FCR Calculator Build

echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
python --version

echo [2/4] Installing PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 pip install pyinstaller -q
echo OK

echo [3/4] Installing dependencies...
pip install pandas numpy matplotlib openpyxl PySide6 scipy -q
echo OK

echo [4/4] Building executable (may take 2-5 minutes)...
cd /d "%~dp0"

pyinstaller --noconsole --onefile --name "FCR_Calculator" --distpath "." --workpath "..\build" --specpath "..\build" --collect-all fcr_app --hidden-import pandas --hidden-import numpy --hidden-import matplotlib --hidden-import matplotlib.backends.backend_qtagg --hidden-import matplotlib.backends.backend_agg --hidden-import openpyxl --hidden-import PySide6 --hidden-import scipy --hidden-import sklearn fcr_main.py

if errorlevel 1 (
    echo ERROR: Build failed!
) else (
    echo =====================
    echo BUILD SUCCESS!
    echo =====================
    echo Output: FCR_Calculator.exe
    if exist "FCR_Calculator.exe" (
        for %%f in ("FCR_Calculator.exe") do echo Size: %%~zf bytes
    )
)

pause
