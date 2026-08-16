@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   TRPG AI 跑团主持 - 一键启动器
echo ============================================================
echo.

:: ---- Find Python (flag pattern: no goto out of for loop) ----
set "PYTHON="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
)

if not defined PYTHON (
    for %%p in (python3 python py) do (
        if not defined PYTHON (
            for /f "delims=" %%a in ('where %%p 2^>nul') do (
                if not defined PYTHON if exist "%%a" set "PYTHON=%%a"
            )
        )
    )
)

if not defined PYTHON (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined PYTHON if exist %%d set "PYTHON=%%d"
    )
)

if not defined PYTHON (
    echo [FAIL] Python not found. Install Python 3.11+ first.
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python: !PYTHON!

:: ---- Install Python deps if needed ----
"%PYTHON%" -c "import fastapi,uvicorn,openai,sqlalchemy,aiosqlite,pydantic,dotenv" >nul 2>&1
if errorlevel 1 (
    echo [..] Installing Python deps...
    "%PYTHON%" -m pip install -r "%~dp0backend\requirements.txt" -q --disable-pip-version-check
    if errorlevel 1 (
        "%PYTHON%" -m pip install openai fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" aiosqlite pydantic python-dotenv sse-starlette -q -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    )
    echo [OK] Python deps installed
) else (
    echo [OK] Python deps ready
)

:: ---- Check Node.js ----
set "FRONTEND=0"
where node >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found, backend only
    goto :skip_frontend
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [WARN] npm not found, backend only
    goto :skip_frontend
)

cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [..] npm install...
    call npm install
)
if exist "node_modules" (
    set "FRONTEND=1"
    echo [OK] Frontend deps ready
) else (
    echo [WARN] npm install failed, backend only
)
cd /d "%~dp0"

:skip_frontend

:: ---- Kill existing servers on ports ----
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" 2^>nul ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" 2^>nul ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: ---- Start backend ----
echo.
echo ============================================================
echo   Starting servers...
echo ============================================================

set "BS=%~dp0_backend_launch.bat"
> "!BS!" echo @echo off
>>"!BS!" echo cd /d "%~dp0"
>>"!BS!" echo "!PYTHON!" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
start "AI-DM-Backend" /MIN "!BS!"
echo [OK] Backend launched

:: Wait for backend
set "READY=0"
for /l %%i in (1,1,30) do (
    curl -sf http://127.0.0.1:8000/api/health >nul 2>&1
    if not errorlevel 1 (
        set "READY=1"
        goto :backend_ready
    )
    ping -n 3 127.0.0.1 >nul
)
:backend_ready
if "!READY!"=="1" (
    echo [OK] Backend ready  - http://localhost:8000
) else (
    echo [WARN] Backend may still be loading, check http://localhost:8000/docs
)

:: ---- Start frontend ----
if "!FRONTEND!"=="1" (
    set "FS=%~dp0_frontend_launch.bat"
    > "!FS!" echo @echo off
    >>"!FS!" echo cd /d "%~dp0frontend"
    >>"!FS!" echo npx vite --host 127.0.0.1 --port 5173
    start "AI-DM-Frontend" /MIN "!FS!"
    echo [OK] Frontend launched
    ping -n 4 127.0.0.1 >nul
    start "" http://localhost:5173
)

:: ---- Done ----
echo.
echo ============================================================
echo   ALL SET! Open http://localhost:5173 in your browser
echo   Press any key here to STOP all servers
echo ============================================================
pause >nul

:: ---- Cleanup ----
taskkill /FI "WINDOWTITLE eq AI-DM-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-DM-Frontend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" 2^>nul ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" 2^>nul ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
del "%~dp0_backend_launch.bat" >nul 2>&1
del "%~dp0_frontend_launch.bat" >nul 2>&1
echo All servers stopped.
endlocal
