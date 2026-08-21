#!/usr/bin/env bash
#
# Image MultiModel - Start Script (Linux/macOS)
#
# Detects Python 3.10+ and launches the application.
#
# Usage:
#   chmod +x start.sh
#   ./start.sh
#

set -e

echo "============================================================"
echo "  Image MultiModel - Multi-Model AI Image Generation"
echo "============================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# ── Detect Python interpreter ──────────────────────────
PYTHON_CMD=""

# 1. Try python3.12, python3.11, python3.10
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &> /dev/null; then
        ver=$("$cmd" --version 2>&1 | head -1)
        major_minor=$(echo "$ver" | grep -oP '3\.\d+' || true)
        if [ -n "$major_minor" ]; then
            major=$(echo "$major_minor" | cut -d. -f1)
            minor=$(echo "$major_minor" | cut -d. -f2)
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON_CMD="$cmd"
                echo "[OK] Found Python: $ver ($cmd)"
                break
            fi
        fi
    fi
done

# 2. Fallback: check common paths
if [ -z "$PYTHON_CMD" ]; then
    for path in /usr/bin/python3.12 /usr/local/bin/python3.12 /opt/python3.12/bin/python3.12 \
                /usr/bin/python3.11 /usr/local/bin/python3.11 \
                /usr/bin/python3.10 /usr/local/bin/python3.10; do
        if [ -x "$path" ]; then
            PYTHON_CMD="$path"
            echo "[OK] Found Python at: $path"
            break
        fi
    done
fi

# 3. No Python found
if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] Python 3.10+ not found!"
    echo ""
    echo "============================================================"
    echo "  Please install Python 3.10+ (3.12 recommended):"
    echo "============================================================"
    echo ""
    echo "  Ubuntu/Debian:"
    echo "    sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip"
    echo ""
    echo "  macOS (Homebrew):"
    echo "    brew install python@3.12"
    echo ""
    echo "  Then run install.sh to install dependencies."
    echo ""
    echo "============================================================"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
echo ""

# Check launch script
if [ ! -f "app/clean_launch.py" ]; then
    echo "Error: Launch script not found at app/clean_launch.py"
    exit 1
fi

echo "Starting Image MultiModel..."
echo ""

"$PYTHON_CMD" app/clean_launch.py
