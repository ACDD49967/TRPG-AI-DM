@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "OUTDIR=%~dp0dist"
set "NAME=AI-Dungeon-Master"
set "PKG=%OUTDIR%\%NAME%"
set "ZIP=%OUTDIR%\%NAME%.zip"

echo.
echo ============================================================
echo   Package AI Dungeon Master for Distribution
echo ============================================================
echo.

if exist "%OUTDIR%" (
    echo [..] Cleaning old dist...
    rmdir /s /q "%OUTDIR%" 2>nul
)

mkdir "%OUTDIR%"
mkdir "%PKG%"

echo [1/3] Copying files (excluding .venv / node_modules / cache / db / .env)...

robocopy "%~dp0." "%PKG%" ^
    /E /NDL /NJH /NJS ^
    /XF *.db *.db-journal *.db-wal *.pyc .DS_Store ^
    /XF .env _test.bat _backend_launch.bat _frontend_launch.bat ^
    /XD .venv .idea __pycache__ .git .claude frontend\node_modules dist

if errorlevel 8 (
    echo [FAIL] robocopy error
    pause
    exit /b 1
)
echo [OK] Files copied

REM Recursively kill __pycache__
for /d /r "%PKG%" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d" 2>nul
)
for /r "%PKG%" %%f in (*.pyc .DS_Store) do (
    del "%%f" >nul 2>&1
)

echo [2/3] Verifying CRLF on .bat files...
REM robocopy preserves line endings natively on Windows -> already CRLF
REM but verify by checking first line doesn't contain garbage
for %%f in ("%PKG%\*.bat") do (
    echo       %%~nxf
)

echo [3/3] Creating zip archive...
powershell -NoProfile -Command "Compress-Archive -Path '%PKG%' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
    echo [FAIL] Zip creation failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Package created!
echo   %ZIP%
echo ============================================================
echo.
echo   Included:
echo     - backend/        Python FastAPI source
echo     - frontend/       React + Vite source + dist/
echo     - scenarios/      Sample adventures
echo     - setup.bat/.sh   One-click init
echo     - run.bat/.sh     One-click launch
echo     - README.md       Full docs
echo     - .env.example    API key template
echo.
echo   Excluded:
echo     - .venv/ node_modules/ __pycache__/
echo     - dndgame.db  .env  .idea/
echo.
echo   Recipient steps:
echo     1. Unzip
echo     2. Double-click setup.bat
echo     3. Edit .env - add API key
echo     4. Double-click run.bat
echo.
pause
