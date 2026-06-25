@echo off
chcp 65001 >nul
title BELLA AI - Cài đặt thư viện
echo.
echo ============================================
echo   BELLA AI Script Generator
echo   Đang cài đặt thư viện Python...
echo ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Python chưa được cài đặt!
    echo Tải Python tại: https://www.python.org/downloads/
    echo Nhớ tích "Add Python to PATH" khi cài.
    pause
    exit /b 1
)

echo [OK] Python đã được cài.
echo.
echo Đang cài thư viện...
pip install flask openai google-generativeai

echo.
echo ============================================
echo   Cài đặt xong! Chạy file 2_CHAY_TOOL.bat
echo ============================================
pause
