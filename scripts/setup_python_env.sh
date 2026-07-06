#!/bin/bash
# Setup Python Environment - Bash Script
# Usage: bash scripts/setup_python_env.sh [--dev]

set -e  # Exit on error

DEV=false
if [[ "$1" == "--dev" || "$1" == "-dev" ]]; then
    DEV=true
fi

echo "========================================"
echo "DB_LIBRARY_EDIT - Python Environment Setup"
echo "========================================"
echo ""

# Step 1: Check Python
echo "[1/5] Checking Python..."
PYTHON_CMD=""
for cmd in python3 python py; do
    if command -v $cmd &> /dev/null; then
        VERSION=$($cmd --version 2>&1)
        echo "  Found: $cmd -> $VERSION"
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "  ERROR: Python not found. Please install Python 3.x"
    exit 1
fi

# Step 2: Create .venv if not exist
echo "[2/5] Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  .venv already exists, skipping creation"
else
    echo "  Creating .venv..."
    $PYTHON_CMD -m venv .venv
    echo "  .venv created successfully"
fi

# Step 3: Activate .venv
echo "[3/5] Activating environment..."
source .venv/bin/activate
echo "  Environment activated"

# Step 4: Upgrade pip, setuptools, wheel
echo "[4/5] Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel -q || {
    echo "  WARNING: Failed to upgrade pip/setuptools/wheel"
}
echo "  Upgraded successfully"

# Step 5: Install requirements
echo "[5/5] Installing requirements..."
if [ "$DEV" = true ]; then
    echo "  Installing production + development packages..."
    pip install -q -r requirements.txt -r requirements-dev.txt
    echo "  Development packages installed"
else
    echo "  Installing production packages..."
    pip install -q -r requirements.txt
    echo "  Production packages installed"
fi

echo ""
echo "========================================"
echo "Setup completed successfully!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Verify environment: python scripts/smoke_test.py"
echo "  2. Add --dev flag to install dev packages: bash scripts/setup_python_env.sh --dev"
echo ""
