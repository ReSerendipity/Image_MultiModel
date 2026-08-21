#!/usr/bin/env bash
#
# Image MultiModel - Installation Script (Linux/macOS)
#
# This script will:
#   1. Check Python environment (Python 3.10+)
#   2. Install PyTorch + all required dependencies
#   3. Create required directories
#
# Usage:
#   chmod +x install.sh
#   ./install.sh
#

set -e

echo "============================================================"
echo "  Image MultiModel - Installation Script"
echo "============================================================"
echo ""
echo "This script will:"
echo "  1. Check Python environment (Python 3.10+)"
echo "  2. Install PyTorch + all required dependencies"
echo "  3. Create required directories"
echo ""
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
        # Extract major.minor
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
    echo "  Or download from: https://www.python.org/downloads/"
    echo ""
    echo "============================================================"
    exit 1
fi

echo ""
echo "============================================================"
echo "  Step 1: Installing Python Dependencies"
echo "============================================================"
echo ""
echo "Using Python: $PYTHON_CMD"
"$PYTHON_CMD" --version
echo ""

# Upgrade pip
echo "Upgrading pip..."
"$PYTHON_CMD" -m pip install --upgrade pip

# Install PyTorch with CUDA (Linux)
echo ""
echo "Installing PyTorch with CUDA support..."
echo "  If download is too slow, you can install CPU-only version instead:"
echo "  pip install torch torchvision torchaudio"
echo ""

# Try CUDA version first, fall back to CPU on failure
if ! "$PYTHON_CMD" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --timeout 1200 --retries 3 2>/dev/null; then
    echo "[WARNING] CUDA PyTorch installation failed, trying CPU version..."
    "$PYTHON_CMD" -m pip install torch torchvision torchaudio --timeout 600 --retries 3
fi

echo ""
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    "$PYTHON_CMD" -m pip install -r requirements.txt --timeout 300 --retries 3
    echo "[OK] Dependencies installed successfully"
else
    echo "[WARNING] requirements.txt not found, skipping dependency installation"
fi

echo ""
echo "============================================================"
echo "  Step 2: Creating Required Directories"
echo "============================================================"
echo ""

mkdir -p data/presets
mkdir -p data/uploads
mkdir -p data/cache
mkdir -p outputs
mkdir -p logs
mkdir -p model/checkpoints
mkdir -p model/controlnet
mkdir -p model/loras
mkdir -p model/text_encoders
mkdir -p model/unet
mkdir -p model/vae
mkdir -p workflows

echo "[OK] Required directories created"

echo ""
echo "============================================================"
echo "  Installation Complete!"
echo "============================================================"
echo ""
echo "You can now start the application by running:"
echo "  ./start.sh"
echo "  # or"
echo "  python app/clean_launch.py"
echo ""
echo "Note: Make sure your ComfyUI workflows (.json) are in workflows/"
echo "and model checkpoints are properly configured in config.yaml."
echo ""
