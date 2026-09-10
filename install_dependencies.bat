@echo off
cd /d "%~dp0"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo Python 3 was not found. Install Python 3.11 or newer, then run this file again.
            pause
            exit /b 1
        )
        python -m venv .venv
    )
)

"%VENV_PYTHON%" -m pip install --editable ".[dev]"
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo Dependencies installed successfully.
pause
