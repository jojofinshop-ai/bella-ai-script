@echo off
title BELLA AI - Build EXE
cd /d "%~dp0"
echo.
echo ============================================
echo   BELLA AI - Building EXE
echo   This may take 3-10 minutes...
echo ============================================
echo.

set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PYTHON%" (
    where python >nul 2>&1
    if %errorlevel% == 0 ( set "PYTHON=python" )
)

echo Installing dependencies...
"%PYTHON%" -m pip install pyinstaller pythonnet >nul 2>&1

echo Building...
"%PYTHON%" -m PyInstaller --noconfirm BELLA_AI_Script.spec

echo.
if exist "dist\BELLA_AI_Script.exe" (
    echo ============================================
    echo   BUILD SUCCESS!
    echo   File: dist\BELLA_AI_Script.exe
    echo   Copy that file to any Windows machine.
    echo ============================================
    explorer dist
) else (
    echo BUILD FAILED. Check errors above.
)
pause
