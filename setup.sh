#!/usr/bin/env bash
# TRPG AI 跑团主持 — One-Click Setup (Linux/macOS/Git Bash/WSL)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 修复 npm 缓存写入系统目录导致的 EPERM
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$HOME/.npm-cache}"
mkdir -p "$NPM_CONFIG_CACHE"

echo ""
echo "============================================================"
echo "  TRPG AI 跑团主持 - 一键初始化"
echo "============================================================"
echo ""

# ── 1. Check Python ──
echo "[1/5] Checking Python..."

# Prefer bundled .venv
if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
    echo "[OK] Found bundled .venv"
elif [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"
    echo "[OK] Found bundled .venv (Windows-style)"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    echo "[OK] Found: python3"
elif command -v python &>/dev/null; then
    PYTHON="$(command -v python)"
    echo "[OK] Found: python"
else
    echo "[FAIL] Python 3.11+ not found."
    echo "       macOS:  brew install python@3.12"
    echo "       Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "       Or:     https://www.python.org/downloads/"
    exit 1
fi

"$PYTHON" --version

# ── 2. Create .env if missing ──
echo ""
echo "[2/5] Checking .env config..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "[WARN] .env created from template."
        echo "       PLEASE edit .env and add your LLM_API_KEY!"
        echo "       Get a key at: https://platform.deepseek.com/api_keys"
    else
        echo "[WARN] No .env or .env.example found."
    fi
else
    echo "[OK] .env found"
fi

# ── 3. Create venv if missing ──
echo ""
echo "[3/5] Setting up Python virtual environment..."
if [ ! -f "$SCRIPT_DIR/.venv/bin/python3" ] && [ ! -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    echo "[..] Creating virtual environment..."
    "$PYTHON" -m venv "$SCRIPT_DIR/.venv"
    if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
        PYTHON="$SCRIPT_DIR/.venv/bin/python3"
    else
        PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"
    fi
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment ready"
fi

# ── 4. Install Python deps ──
echo ""
echo "[4/5] Installing Python packages..."
if ! "$PYTHON" -c "import fastapi,uvicorn,openai,sqlalchemy,aiosqlite,pydantic,dotenv" 2>/dev/null; then
    echo "[..] Downloading and installing..."
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/backend/requirements.txt" -q --disable-pip-version-check || \
    "$PYTHON" -m pip install fastapi httpx json-repair jieba rank-bm25 numpy "uvicorn[standard]" anthropic "sqlalchemy[asyncio]" aiosqlite pydantic python-dotenv sse-starlette \
        -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    echo "[OK] Python dependencies installed"
else
    echo "[OK] Python dependencies ready"
fi

# ── 5. Frontend ──
echo ""
echo "[5/5] Checking frontend..."
if ! command -v node &>/dev/null; then
    echo "[WARN] Node.js not found — frontend unavailable."
    echo "       Install from: https://nodejs.org/ (LTS)"
    echo "       macOS: brew install node"
    echo "       Ubuntu: sudo apt install nodejs npm"
elif ! command -v npm &>/dev/null; then
    echo "[WARN] npm not found"
else
    cd "$SCRIPT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
        echo "[..] npm install..."
        npm install && echo "[OK] Frontend ready" || echo "[WARN] npm install failed"
    else
        echo "[OK] Frontend ready"
    fi
    cd "$SCRIPT_DIR"
fi

# ── Done ──
echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo ""
echo "  To start the game:"
echo "    Windows:  double-click run.bat"
echo "    macOS/Linux:  bash run.sh"
echo "============================================================"
echo ""