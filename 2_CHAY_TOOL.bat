@echo off
set "PYTHONW=C:\Users\Admin\AppData\Local\Programs\Python\Python311\pythonw.exe"
set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0app.py"
    exit /b 0
)

if exist "%PYTHON%" (
    start "" "%PYTHON%" "%~dp0app.py"
    exit /b 0
)

echo Python not found!
pause
