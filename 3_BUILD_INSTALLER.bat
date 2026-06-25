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
"%PYTHON%" -m pip install pyinstaller >nul 2>&1
"%PYTHON%" -m PyInstaller --noconfirm --onefile --windowed --name "BELLA_AI_Script" ^
  --add-data "templates;templates" ^
  --add-data "bella_icon.ico;." ^
  --add-data "bella_icon_512.png;." ^
  --icon "bella_icon.ico" ^
  --hidden-import flask ^
  --hidden-import openai ^
  --hidden-import werkzeug ^
  --hidden-import webview ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import cryptography ^
  --hidden-import cryptography.hazmat.primitives.ciphers.aead ^
  --hidden-import playwright ^
  --hidden-import playwright.sync_api ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --exclude-module clr ^
  --exclude-module pythonnet ^
  --exclude-module webview.platforms.winforms ^
  --exclude-module grpc ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  app.py

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
