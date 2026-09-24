@echo off
cd /d "%~dp0"
set "REVIEW_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%REVIEW_PYTHON%" (
    echo Project environment not found. Run install_dependencies.bat first.
    pause
    exit /b 1
)
"%REVIEW_PYTHON%" -m financial_statement_extract.ui.review %*
if errorlevel 1 pause
