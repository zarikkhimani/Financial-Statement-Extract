@echo off
cd /d "%~dp0"
set "PREVIEW_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PREVIEW_PYTHON%" (
    echo Project environment not found. Run install_dependencies.bat first.
    pause
    exit /b 1
)

"%PREVIEW_PYTHON%" -m financial_statement_extract.ui.preview %*
if errorlevel 1 pause
