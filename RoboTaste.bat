@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: RoboTaste Launcher — double-click to start all services with pump

cd /d "%~dp0"

if not exist "start_new_ui.py" (
    echo [Launcher] start_new_ui.py was not found in: %~dp0
    echo [Launcher] RoboTaste.bat must stay inside the RoboTaste project folder.
    echo [Launcher] To launch from Desktop, create a shortcut to this file instead of copying it.
    pause
    exit /b 1
)

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
        echo [Update]   [1] Update now ^(git pull --ff-only^)
        echo [Update]   [2] Continue without updating
        choice /C 12 /N /M "Select option [1-2]: "
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

:: Open browser automatically once localhost server responds
set TARGET_URL=http://localhost:8000/
set CHROME_EXE=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe
)

where powershell >nul 2>&1
if errorlevel 1 (
    echo [Launcher] PowerShell not found. Opening default browser now.
    start "" "%TARGET_URL%"
) else (
    if defined CHROME_EXE (
        echo [Launcher] Chrome will open automatically at %TARGET_URL%
    ) else (
        echo [Launcher] Chrome not found. Default browser will open at %TARGET_URL%
    )
    start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url='%TARGET_URL%'; $chrome='%CHROME_EXE%'; for($i=0;$i -lt 240;$i++){ try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200){ if($chrome -and (Test-Path $chrome)){ Start-Process -FilePath $chrome -ArgumentList '--new-window', $url } else { Start-Process $url }; exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; if($chrome -and (Test-Path $chrome)){ Start-Process -FilePath $chrome -ArgumentList '--new-window', $url } else { Start-Process $url }"
)

echo [Launcher] Starting RoboTaste with pump service...
%PYTHON% start_new_ui.py --with-pump
set RUN_STATUS=%ERRORLEVEL%

if not "%RUN_STATUS%"=="0" (
    echo.
    echo [Launcher] Startup with pump failed ^(exit code %RUN_STATUS%^).
    echo [Launcher] Retrying without pump service...
    %PYTHON% start_new_ui.py
    set RUN_STATUS=%ERRORLEVEL%
)

if not "%RUN_STATUS%"=="0" (
    echo [Launcher] RoboTaste exited with code %RUN_STATUS%.
)

pause
exit /b %RUN_STATUS%
