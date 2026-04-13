@echo off
:: RoboTaste Launcher — double-click to start all services with pump

cd /d "%~dp0"

:: Find Python: venv > .venv > system python
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Using Python: %PYTHON%
echo Project: %~dp0
echo.

%PYTHON% start_new_ui.py --with-pump
pause
