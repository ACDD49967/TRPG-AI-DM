@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
:: 修复 npm 缓存写入系统目录导致的 EPERM
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "NPM_CONFIG_CACHE=%LOCALAPPDATA%\npm-cache"
if not exist "%NPM_CONFIG_CACHE%" mkdir "%NPM_CONFIG_CACHE%"
echo   TRPG AI 跑团主持 - 一键初始化
echo ============================================================
echo.

:: =============================================================
:: Step 1 — Find a working Python
:: =============================================================
echo [1/5] Locating Python...
set "PYTHON="
set "PYTHON_LAUNCHER="
set "PYTHON_ARGS="
set "HAS_VENV=1"

:: Already have project .venv?
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
    echo [OK] Project .venv
    goto :python_ok
)

:: Priority 1: py.exe launcher
for %%p in ("C:\Windows\py.exe" "%windir%\py.exe") do (
    if not defined PYTHON if exist %%p (
        :: Get actual Python 3 path from py
        for /f "delims=" %%a in ('%%~p -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%a" set "PYTHON=%%a"
        )
        if defined PYTHON (
            echo [OK] Found via py.exe: !PYTHON!
            goto :python_ok
        )
        :: Can't resolve path but py.exe works — use it directly
        set "PYTHON_LAUNCHER=%%~p"
        set "PYTHON=%%~p"
        set "PYTHON_ARGS=-3"
        echo [OK] Using py.exe -3
        goto :python_ok
    )
)

:: Priority 2: PATH search with validation
for %%p in (python3 python py) do (
    if not defined PYTHON (
        for /f "delims=" %%a in ('where %%p 2^>nul') do (
            if not defined PYTHON if exist "%%a" (
                2>nul "%%a" -c "print('OK')" | findstr "OK" >nul
                if not errorlevel 1 set "PYTHON=%%a"
            )
        )
    )
)

:: Priority 3: common install paths
if not defined PYTHON (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined PYTHON if exist %%d (
            2>nul "%%d" -c "print('OK')" | findstr "OK" >nul
            if not errorlevel 1 set "PYTHON=%%d"
        )
    )
)

if not defined PYTHON (
    echo [FAIL] No working Python 3.11+ found.
    echo        Install from: https://www.python.org/downloads/
    echo        CHECK "Add Python to PATH" during install
    pause
    exit /b 1
)

:python_ok
echo [OK] !PYTHON! !PYTHON_ARGS!

:: =============================================================
:: Step 2 — .env config
:: =============================================================
echo.
echo [2/5] Config...
if exist "%~dp0.env" (
    echo [OK] .env found
) else (
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
        echo [WARN] .env created from template - EDIT IT with your API key
    ) else (
        echo [WARN] No .env.example found
    )
)

:: =============================================================
:: Step 3 — Create virtual environment (error-capturing + fallbacks)
:: =============================================================
echo.
echo [3/5] Virtual environment...

if exist "%~dp0.venv\Scripts\python.exe" (
    echo [OK] Already exists
    goto :install_deps
)

:: ── Can we write here? ──
set "TDIR=%~dp0"
echo. > "%TDIR%_wtest" 2>nul
if not exist "%TDIR%_wtest" (
    echo [FAIL] Cannot write to project folder.
    echo        Move the folder to Desktop or Documents and re-run.
    pause
    exit /b 1
)
del "%TDIR%_wtest" 2>nul

:: ── Attempt 1: python -m venv ──
set "ELOG=%TDIR%_venv_err.txt"
echo [..] Attempt 1: python -m venv .venv
"%PYTHON%" %PYTHON_ARGS% -m venv "%~dp0.venv" >"%ELOG%" 2>&1
if exist "%~dp0.venv\Scripts\python.exe" goto :venv_done
if exist "%~dp0.venv\Scripts\python3.exe" goto :venv_done
if exist "%~dp0.venv\bin\python3" goto :venv_done
set "E1=%errorlevel%"

:: ── Attempt 2: --without-pip (ensurepip bootstraps pip, this step often fails) ──
echo [..] Attempt 2: python -m venv .venv --without-pip
del /f /q "%~dp0.venv" 2>nul
rmdir /s /q "%~dp0.venv" 2>nul
"%PYTHON%" %PYTHON_ARGS% -m venv "%~dp0.venv" --without-pip >"%ELOG%" 2>&1
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [..] Bootstrapping pip manually...
    "%~dp0.venv\Scripts\python.exe" -m ensurepip --upgrade >"%ELOG%" 2>&1
    2>nul "%~dp0.venv\Scripts\python.exe" -m pip --version >nul 2>&1
    if not errorlevel 1 goto :venv_done
    :: pip bootstrap failed but venv exists — mark as venv_no_pip
    echo [WARN] Venv created but pip unavailable — will use system Python for deps
    rmdir /s /q "%~dp0.venv" 2>nul
)
set "E2=%errorlevel%"

:: ── Attempt 3: virtualenv (external package, more tolerant) ──
echo [..] Attempt 3: virtualenv fallback
del /f /q "%~dp0.venv" 2>nul
rmdir /s /q "%~dp0.venv" 2>nul
"%PYTHON%" %PYTHON_ARGS% -m pip install virtualenv -q --disable-pip-version-check >"%ELOG%" 2>&1
if errorlevel 1 (
    "%PYTHON%" %PYTHON_ARGS% -m pip install virtualenv -q -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com >"%ELOG%" 2>&1
)
"%PYTHON%" %PYTHON_ARGS% -m virtualenv "%~dp0.venv" >"%ELOG%" 2>&1
if exist "%~dp0.venv\Scripts\python.exe" goto :venv_done
if exist "%~dp0.venv\bin\python3" goto :venv_done

:: ── All attempts failed: show actual error ──
rmdir /s /q "%~dp0.venv" 2>nul
echo.
echo ============================================================
echo [FAIL] Virtual environment creation failed.
echo.
echo --- Error from last attempt ---
type "%ELOG%" 2>nul
echo --- End of error ---
echo.
echo Manual fix options:
echo.
echo   (1) Open a terminal in this folder and run:
echo       "%PYTHON%" -m venv .venv
echo       Then re-run setup.bat — it will skip venv creation.
echo.
echo   (2) If that also fails, install without venv:
echo       "%PYTHON%" -m pip install --user -r backend\requirements.txt
echo       Then use system Python in run.bat.
echo.
echo   (3) On Debian/Ubuntu:  sudo apt install python3-venv
echo.
del "%ELOG%" 2>nul
pause
exit /b 1

:venv_done
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "!PYTHON!" (
    if exist "%~dp0.venv\bin\python3" set "PYTHON=%~dp0.venv\bin\python3"
)
del "%ELOG%" 2>nul
echo [OK] Virtual environment created: !PYTHON!

:: =============================================================
:: Step 4 — Install Python dependencies
:: =============================================================
:install_deps
echo.
echo [4/5] Python packages...
"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Venv python.exe is broken — removing and please re-run setup.
    rmdir /s /q "%~dp0.venv" 2>nul
    pause
    exit /b 1
)

"%PYTHON%" -c "import fastapi,uvicorn,openai,sqlalchemy,aiosqlite,pydantic,dotenv" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Already installed
    goto :frontend
)

echo [..] Installing...
"%PYTHON%" -m pip install -r "%~dp0backend\requirements.txt" -q --disable-pip-version-check
if errorlevel 1 (
    echo [..] Primary failed — trying mirror...
    "%PYTHON%" -m pip install openai httpx json-repair jieba rank-bm25 numpy langgraph fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" aiosqlite pydantic python-dotenv sse-starlette -q -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
)
echo [OK] Installed

:: =============================================================
:: Step 5 — Frontend
:: =============================================================
:frontend
echo.
echo [5/5] Frontend...
where node >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found — backend only
    echo        http://localhost:8000/docs
    goto :done
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [WARN] npm not found
    goto :done
)

cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [..] npm install...
    call npm install
    if errorlevel 1 (
        echo [WARN] npm install failed
        cd /d "%~dp0"
        goto :done
    )
)
echo [OK] Frontend ready
cd /d "%~dp0"

:done
echo.
echo ============================================================
echo   SETUP COMPLETE — now double-click run.bat
echo ============================================================
echo.
pause
