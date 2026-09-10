#!/usr/bin/env bash
# TRPG AI 跑团主持 - one-click launcher for bash / Git Bash / WSL
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 修复 npm 缓存写入系统目录导致的 EPERM
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$HOME/.npm-cache}"
mkdir -p "$NPM_CONFIG_CACHE"

echo "============================================================"
echo "  TRPG AI 跑团主持 - 一键启动器"
echo "============================================================"
echo ""

# ---- 1. Find Python ----
PYTHON=""
if [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"
    echo "[OK] Using .venv Python (Windows layout)"
elif [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
    echo "[OK] Using .venv Python (Unix layout)"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
    echo "[OK] Using .venv Python (Unix layout)"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    echo "[OK] Using python3: $PYTHON"
elif command -v python &>/dev/null; then
    PYTHON="$(command -v python)"
    echo "[OK] Using python: $PYTHON"
else
    echo "[FAIL] Python not found. Install Python 3.11+"
    echo "       https://www.python.org/downloads/"
    exit 1
fi

"$PYTHON" --version

# ---- 2. Install Python deps ----
if ! "$PYTHON" -c "import fastapi,uvicorn,openai,sqlalchemy,aiosqlite,pydantic,dotenv" 2>/dev/null; then
    echo "[..] Installing Python dependencies..."
    "$PYTHON" -m pip install fastapi "uvicorn[standard]" openai "sqlalchemy[asyncio]" aiosqlite pydantic python-dotenv sse-starlette -q --disable-pip-version-check || \
    "$PYTHON" -m pip install fastapi "uvicorn[standard]" openai "sqlalchemy[asyncio]" aiosqlite pydantic python-dotenv sse-starlette -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    echo "[OK] Python deps installed"
else
    echo "[OK] Python deps ready"
fi

# ---- 3. Check Node.js ----
FRONTEND=0
if command -v node &>/dev/null && command -v npm &>/dev/null; then
    cd "$SCRIPT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
        echo "[..] npm install..."
        npm install && FRONTEND=1 || echo "[WARN] npm install failed"
    else
        FRONTEND=1
        echo "[OK] Frontend deps ready"
    fi
    cd "$SCRIPT_DIR"
else
    echo "[WARN] Node.js not found, backend only"
fi

# ---- 4. Kill old servers（跨平台）----
echo "[..] Checking for running servers..."
kill_port() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        local pids
        pids="$(lsof -ti "tcp:$port" 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            kill $pids 2>/dev/null || true
            echo "[OK] Killed old process on port $port"
            return
        fi
    fi
    if command -v fuser &>/dev/null; then
        fuser -k "${port}/tcp" 2>/dev/null && echo "[OK] Killed old process on port $port" && return
    fi
    if command -v netstat &>/dev/null && command -v taskkill &>/dev/null; then
        local pid
        pid="$(netstat -ano 2>/dev/null | grep ":$port" | grep "LISTENING" | awk '{print $5}' | head -1)"
        if [ -n "$pid" ]; then
            taskkill //PID "$pid" //F 2>/dev/null || true
            echo "[OK] Killed old process on port $port"
        fi
    fi
}
for port in 8000 5173; do
    kill_port "$port"
done
sleep 1

# ---- 5. Start backend ----
echo ""
echo "============================================================"
echo "  Starting servers..."
echo "============================================================"

FRONTEND_PID=""
"$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-level warning &
BACKEND_PID=$!
echo "[OK] Backend PID: $BACKEND_PID"

# Wait for backend
echo -n "[..] Waiting for backend..."
for i in $(seq 1 20); do
    if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        echo ""
        echo "[OK] Backend ready - http://localhost:8000"
        break
    fi
    echo -n "."
    sleep 1.5
done

# ---- 6. Start frontend ----
if [ "$FRONTEND" -eq 1 ]; then
    cd "$SCRIPT_DIR/frontend"
    npx vite --host 127.0.0.1 --port 5173 &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
    echo "[OK] Frontend PID: $FRONTEND_PID"
    sleep 2
    # Open browser（跨平台）
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:5173" >/dev/null 2>&1 || true
    elif command -v open &>/dev/null; then
        open "http://localhost:5173" >/dev/null 2>&1 || true
    elif command -v cmd.exe &>/dev/null; then
        cmd.exe /c start "" "http://localhost:5173" >/dev/null 2>&1 || true
    fi
fi

# ---- Done ----
echo ""
echo "============================================================"
echo "  READY!"
echo "  Game UI:  http://localhost:5173"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all servers"
echo "============================================================"

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID 2>/dev/null; [ -n \"$FRONTEND_PID\" ] && kill $FRONTEND_PID 2>/dev/null; echo 'Bye!'; exit 0" INT TERM

# Keep the script running so Ctrl+C works
while true; do
    sleep 1
    # If backend died, exit
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "[WARN] Backend stopped unexpectedly"
        break
    fi
done
