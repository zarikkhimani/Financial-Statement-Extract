@echo off
cd /d "%~dp0"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo Project environment not found. Run install_dependencies.bat first.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m financial_statement_extract.gui
if errorlevel 1 pause
