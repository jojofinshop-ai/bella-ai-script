@echo off
title BELLA AI - Build Installer
cd /d "%~dp0"
echo.
echo ============================================
echo   BELLA AI - Build Installer
echo   Step 1: Build EXE with PyInstaller
echo   Step 2: Package into Setup installer
echo ============================================
echo.

set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not exist "%PYTHON%" (
    where python >nul 2>&1
    if %errorlevel% == 0 ( set "PYTHON=python" ) else (
        echo ERROR: Python not found!
        pause & exit /b 1
    )
)

if not exist "%ISCC%" (
    echo ERROR: Inno Setup not found at %ISCC%
    echo Please install Inno Setup 6 from https://jrsoftware.org
    pause & exit /b 1
)

echo [1/2] Building EXE with PyInstaller...
echo.
"%PYTHON%" -m pip install pyinstaller pythonnet >nul 2>&1
"%PYTHON%" -m PyInstaller --noconfirm BELLA_AI_Script.spec

if not exist "dist\BELLA_AI_Script.exe" (
    echo.
    echo ERROR: PyInstaller build failed! Check errors above.
    pause & exit /b 1
)

echo.
echo [2/2] Creating installer with Inno Setup...
echo.
if not exist "installer_output" mkdir "installer_output"
"%ISCC%" bella_installer.iss

echo.
if exist "installer_output\BELLA_AI_Setup.exe" (
    echo ============================================
    echo   BUILD SUCCESS!
    echo.
    echo   Installer: installer_output\BELLA_AI_Setup.exe
    echo   Chia se file nay cho bat ky may tinh nao.
    echo ============================================
    explorer "installer_output"
) else (
    echo BUILD FAILED. Check errors above.
)
pause
