#!/usr/bin/env bash
# VLA-Pilot++ One-Shot Setup Script
# Run once from the project root: bash setup.sh

set -e
cd "$(dirname "$0")"

echo "=== VLA-Pilot++ Setup ==="

# ── 1. Submodules ──────────────────────────────────────────────────────────────
echo "[1/5] Initialising git submodules..."
git submodule update --init --recursive

# ── 2. Conda environment ───────────────────────────────────────────────────────
echo "[2/5] Creating conda environment 'vla-pilot'..."
if conda env list | grep -q "^vla-pilot "; then
    echo "  Environment 'vla-pilot' already exists — skipping creation."
    echo "  To recreate: conda env remove -n vla-pilot && bash setup.sh"
else
    conda env create -f environment.yml
fi

# Activate inside the script via conda's shell functions
eval "$(conda shell.bash hook)"
conda activate vla-pilot

# ── 3. Third-party editable installs ──────────────────────────────────────────
echo "[3/5] Installing third-party packages in editable mode..."

if [ -d "third_party/calvin/calvin_env" ]; then
    pip install -e third_party/calvin/calvin_env --quiet
    echo "  ✓ calvin_env"
fi

if [ -d "third_party/calvin/calvin_models" ]; then
    pip install -e third_party/calvin/calvin_models --quiet
    echo "  ✓ calvin_models"
fi

if [ -d "third_party/lerobot" ]; then
    pip install -e third_party/lerobot --quiet
    echo "  ✓ lerobot"
fi

if [ -d "third_party/libero_pro" ]; then
    pip install -e third_party/libero_pro --quiet
    echo "  ✓ libero_pro"
fi

if [ -d "third_party/rdt" ]; then
    cd third_party/rdt && pip install -r requirements.txt --quiet && cd -
    echo "  ✓ rdt"
fi

# ── 4. Ensure dotenv is available ─────────────────────────────────────────────
echo "[4/5] Ensuring python-dotenv is installed..."
pip install python-dotenv --quiet

# ── 5. .env check ─────────────────────────────────────────────────────────────
echo "[5/5] Checking .env..."
if grep -q "YOUR_API_KEY_HERE" .env; then
    echo ""
    echo "  ⚠️  ACTION REQUIRED: open .env and replace YOUR_API_KEY_HERE with your Poe API key."
    echo ""
else
    echo "  ✓ .env looks configured."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Run LIBERO:  bash run.sh libero"
echo "Run CALVIN:  bash run.sh calvin"
echo ""
echo "Or directly: conda activate vla-pilot && python main.py"
