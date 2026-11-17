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
            echo Python 3 was not found. Install Python 3.11.5 or newer, then run this file again.
            pause
            exit /b 1
        )
        python -m venv .venv
    )
)

if not exist "%VENV_PYTHON%" (
    echo Python environment creation failed.
    pause
    exit /b 1
)

rem Use the Python security advisory's checksum-pinned pip wheel before index access.
rem https://discuss.python.org/t/109576
"%VENV_PYTHON%" -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --no-deps --upgrade ^
    "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
if errorlevel 1 (
    echo Secure pip bootstrap failed. Project dependencies were not installed.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install --upgrade "pip>=26.2.2" "certifi>=2026.10.19"
if errorlevel 1 (
    echo Packaging and certificate update failed. Project dependencies were not installed.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install --editable ".[dev]"
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo Dependencies installed successfully.
pause
exit /b 0
