#!/usr/bin/env bash
# Package AI Dungeon Master for distribution
# Usage: bash package.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

OUTDIR="$SCRIPT_DIR/dist"
NAME="AI-Dungeon-Master"
PKG="$OUTDIR/$NAME"

echo ""
echo "============================================================"
echo "  Package AI Dungeon Master for Distribution"
echo "============================================================"
echo ""

# ── Clean ──
rm -rf "$OUTDIR"
mkdir -p "$PKG"

# ── Copy (tar preserves exact bytes including CRLF) ──
echo "[1/3] Copying files (excluding .venv / node_modules / cache / db / .env)..."
tar -cf - \
    --exclude='.venv' \
    --exclude='.idea' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='.claude' \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='*.db' \
    --exclude='*.db-journal' \
    --exclude='*.db-wal' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='_test.bat' \
    --exclude='_backend_launch.bat' \
    --exclude='_frontend_launch.bat' \
    -C "$SCRIPT_DIR" . | tar xf - -C "$PKG" 2>/dev/null

# Clean __pycache__ that may have slipped through
find "$PKG" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$PKG" -type f -name '*.pyc' -delete 2>/dev/null || true
find "$PKG" -type f -name '.DS_Store' -delete 2>/dev/null || true

# ── Enforce CRLF on .bat files ──
echo "[2/3] Enforcing CRLF line endings on .bat files..."
for f in "$PKG"/*.bat; do
    if [ -f "$f" ]; then
        sed -i 's/\r\?$/\r/' "$f"
        echo "       $(basename "$f") -> CRLF"
    fi
done

# Also verify .sh files are LF
for f in "$PKG"/*.sh; do
    if [ -f "$f" ]; then
        sed -i 's/\r$//' "$f"
        echo "       $(basename "$f") -> LF"
    fi
done

# ── Create zip ──
echo "[3/3] Creating zip archive..."
cd "$OUTDIR"
if command -v zip &>/dev/null; then
    zip -r "$NAME.zip" "$NAME" -x "*.DS_Store" >/dev/null
elif command -v tar &>/dev/null; then
    tar -caf "$NAME.zip" "$NAME"
else
    powershell -NoProfile -Command "Compress-Archive -Path '$PKG' -DestinationPath '$OUTDIR/$NAME.zip' -Force"
fi
cd "$SCRIPT_DIR"

SIZE=$(ls -lh "$OUTDIR/$NAME.zip" | awk '{print $5}')

echo ""
echo "============================================================"
echo "  Package created!"
echo "  $OUTDIR/$NAME.zip  ($SIZE)"
echo "============================================================"
echo ""
echo "  Included:"
echo "    - backend/          Python FastAPI source"
echo "    - frontend/         React + Vite source + dist/"
echo "    - scenarios/        Sample adventures"
echo "    - setup.bat/.sh     One-click init"
echo "    - run.bat/.sh       One-click launch"
echo "    - README.md         Full docs"
echo "    - .env.example      API key template"
echo ""
echo "  Excluded:"
echo "    - .venv/ node_modules/ __pycache__/"
echo "    - dndgame.db  .env  .idea/"
echo ""
echo "  Recipient steps:"
echo "    1. Unzip"
echo "    2. setup.bat  (or bash setup.sh)"
echo "    3. Edit .env -> add API key"
echo "    4. run.bat    (or bash run.sh)"
echo ""
