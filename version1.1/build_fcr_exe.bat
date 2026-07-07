@echo off
chcp 65001 >nul
title FCR Calculator Build

echo [1/4] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo [2/4] Installing dependencies (this may take 3-5 minutes)...
echo      PyInstaller, pandas, numpy, matplotlib, openpyxl, PySide6, scipy
echo.
pip install pyinstaller pandas numpy matplotlib openpyxl PySide6 scipy
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo OK

echo.
echo [3/4] Cleaning old build...
if exist "..\build" rmdir /s /q "..\build"
if exist "FCR_Calculator.exe" del /f /q "FCR_Calculator.exe"
echo OK

echo.
echo [4/4] Building executable (may take 3-8 minutes)...
echo.
cd /d "%~dp0"

if not exist "fcr_main.py" (
    echo ERROR: fcr_main.py not found!
    pause
    exit /b 1
)

pyinstaller --noconsole --onefile --name "FCR_Calculator" --distpath "." --workpath "..\build" --specpath "..\build" --collect-all fcr_app --hidden-import pandas --hidden-import numpy --hidden-import matplotlib --hidden-import matplotlib.backends.backend_qtagg --hidden-import matplotlib.backends.backend_agg --hidden-import openpyxl --hidden-import PySide6 --hidden-import scipy --hidden-import sklearn fcr_main.py

if errorlevel 1 (
    echo.
    echo =====================
    echo Build FAILED!
    echo =====================
    echo Check the error messages above.
) else (
    echo.
    echo =====================
    echo BUILD SUCCESS!
    echo =====================
    echo Output: FCR_Calculator.exe
    if exist "FCR_Calculator.exe" (
        for %%f in ("FCR_Calculator.exe") do echo Size: %%~zf bytes
    )
)

echo.
pause
