@echo off
setlocal EnableExtensions
:: RoboTaste network backup — invoked by Windows Task Scheduler.
:: Backs up the live DB, logs, and protocols to the shared folder configured
:: in backup_to_network.py (BACKUP_DEST / ROBOTASTE_BACKUP_DEST).

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

"%PYTHON%" scripts\backup_to_network.py %*
exit /b %ERRORLEVEL%
