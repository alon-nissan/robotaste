@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: RoboTaste Launcher — double-click to start all services with pump

cd /d "%~dp0"

:: ─── Optional update check (safe mode: prompt before pull) ──────────────────
where git >nul 2>&1
if errorlevel 1 (
    echo [Update] Git not found. Skipping update check.
    goto :after_update_check
)

if not exist ".git" (
    echo [Update] Not a git checkout. Skipping update check.
    goto :after_update_check
)

git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
    echo [Update] No upstream branch configured. Skipping auto-update.
    goto :after_update_check
)

echo [Update] Checking for updates...
git fetch --prune --quiet >nul 2>&1
if errorlevel 1 (
    echo [Update] Could not reach remote. Continuing with local version.
    goto :after_update_check
)

set AHEAD=0
set BEHIND=0
for /f "tokens=1,2" %%A in ('git rev-list --left-right --count HEAD...@{u} 2^>nul') do (
    set AHEAD=%%A
    set BEHIND=%%B
)

set DIRTY=0
for /f %%A in ('git status --porcelain 2^>nul') do (
    set DIRTY=1
    goto :dirty_done
)
:dirty_done

if "!AHEAD!"=="0" if "!BEHIND!"=="0" (
    echo [Update] Already up to date.
    goto :after_update_check
)

if "!AHEAD!"=="0" if not "!BEHIND!"=="0" (
    if "!DIRTY!"=="0" (
        echo [Update] New remote changes available.
        choice /M "Pull latest changes now"
        if errorlevel 2 (
            echo [Update] Skipped pull.
        ) else (
            git pull --ff-only
            if errorlevel 1 (
                echo [Update] Pull failed. Continuing with current version.
            ) else (
                echo [Update] Updated successfully.
            )
        )
    ) else (
        echo [Update] Remote has updates, but local files are modified.
        echo [Update] Commit/stash local changes first, then run: git pull --ff-only
    )
    goto :after_update_check
)

if not "!AHEAD!"=="0" if "!BEHIND!"=="0" (
    echo [Update] Local branch is ahead of upstream. No pull performed.
    goto :after_update_check
)

echo [Update] Local and remote have diverged. No pull performed.
echo [Update] Resolve with git status / git pull --rebase (or merge) manually.

:after_update_check
echo.

:: Find Python: .venv > venv > system python
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
