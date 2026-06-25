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

echo Installing PyInstaller...
"%PYTHON%" -m pip install pyinstaller >nul 2>&1

echo Building...
"%PYTHON%" -m PyInstaller --noconfirm --onefile --windowed --name "BELLA_AI_Script" ^
  --add-data "templates;templates" ^
  --hidden-import flask ^
  --hidden-import openai ^
  --hidden-import werkzeug ^
  --hidden-import webview ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import cryptography ^
  --hidden-import cryptography.hazmat.primitives.ciphers.aead ^
  --hidden-import playwright ^
  --hidden-import playwright.sync_api ^
  --exclude-module clr ^
  --exclude-module pythonnet ^
  --exclude-module webview.platforms.winforms ^
  --exclude-module google.generativeai ^
  --exclude-module grpc ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  app.py

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
