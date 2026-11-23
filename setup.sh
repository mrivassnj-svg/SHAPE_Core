#!/usr/bin/env bash
# setup.sh — one-shot Raspberry Pi setup for SHAPE
#
# Usage:  chmod +x setup.sh && ./setup.sh
#
# Group 3 — ITAI2376-14562
# Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas

set -e

echo "=== SHAPE Setup for Raspberry Pi ==="

# 1. System packages
echo "[1/5] Installing system packages…"
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv curl git

# 2. Python virtual environment
echo "[2/5] Creating virtual environment…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel

# 3. Python dependencies
echo "[3/5] Installing Python dependencies…"
pip install -r requirements.txt

# 4. Ollama
echo "[4/5] Installing Ollama…"
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "  Ollama already installed."
fi

echo "  Pulling codellama model (~3.8 GB — this may take a while)…"
ollama pull codellama

# 5. Data directories
echo "[5/5] Creating data directories…"
mkdir -p data/docs data/doc_index workspace

echo ""
echo "=== Setup complete! ==="
echo "Start Ollama:  ollama serve"
echo "Run SHAPE:     source .venv/bin/activate && python main.py"
