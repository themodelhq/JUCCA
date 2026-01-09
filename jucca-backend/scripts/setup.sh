#!/bin/bash

# ============================================
# JUCCA Setup Script
# ============================================
# Initial setup and configuration for JUCCA
# ============================================

set -e

# Configuration
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${BACKEND_DIR}/.env"

echo "============================================"
echo "JUCCA Setup Script"
echo "============================================"
echo ""

# Check Python version
echo "[1/6] Checking Python version..."
python_version=$(python --version 2>&1 | cut -d' ' -f2)
major_minor=$(echo "$python_version" | cut -d'.' -f1,2)

if [ "$major_minor" = "3.11" ] || [ "$major_minor" = "3.10" ] || [ "$major_minor" = "3.12" ]; then
    echo "  Python $python_version - OK"
else
    echo "  Warning: Python $python_version may not be fully compatible"
    echo "  Recommended: Python 3.10, 3.11, or 3.12"
fi

# Create virtual environment
echo ""
echo "[2/6] Creating virtual environment..."
if [ ! -d "${BACKEND_DIR}/.venv" ]; then
    python -m venv "${BACKEND_DIR}/.venv"
    echo "  Virtual environment created"
else
    echo "  Virtual environment already exists"
fi

# Install dependencies
echo ""
echo "[3/6] Installing Python dependencies..."
source "${BACKEND_DIR}/.venv/bin/activate"
pip install --upgrade pip
pip install -r "${BACKEND_DIR}/requirements.txt"
echo "  Dependencies installed"

# Create required directories
echo ""
echo "[4/6] Creating directory structure..."
mkdir -p "${BACKEND_DIR}/models"
mkdir -p "${BACKEND_DIR}/data"
mkdir -p "${BACKEND_DIR}/backups"
mkdir -p "${BACKEND_DIR}/monitoring"
mkdir -p "${BACKEND_DIR}/load_testing"
echo "  Directories created"

# Create environment file
echo ""
echo "[5/6] Creating environment configuration..."
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EOF
# JUCCA Configuration
# ====================

# Database
DATABASE_URL=sqlite:///./jucca.db

# LLM Configuration
# Primary: GPT4All (local)
GPT4ALL_MODEL=mistral-7b-openorca.gguf
GPT4ALL_MODEL_PATH=./models

# Cloud Fallback (optional)
# Set OPENAI_API_KEY to enable cloud fallback
OPENAI_API_KEY=
USE_CLOUD_FALLBACK=true
CLOUD_MODEL=gpt-3.5-turbo

# Performance Settings
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=60
STREAMING_ENABLED=true
MAX_CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT_SECONDS=60
OVERLOAD_THRESHOLD=80

# Model Settings
MAX_TOKENS=300
TEMPERATURE=0.7
TOP_P=0.9

# Security
SECRET_KEY=jucca-secret-key-change-in-production
EOF
    echo "  Environment file created: $ENV_FILE"
else
    echo "  Environment file already exists"
fi

# Initialize database
echo ""
echo "[6/6] Initializing database..."
cd "${BACKEND_DIR}"
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/init_db.py
    echo "  Database initialized"
else
    python scripts/init_db.py
    echo "  Database initialized"
fi

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Download GPT4All model: ./scripts/deploy.sh download-model"
echo "  2. Start JUCCA: ./scripts/deploy.sh start"
echo "  3. Access at: http://localhost:8000"
echo ""
echo "Default credentials:"
echo "  Admin: admin / admin123"
echo "  Seller: seller / seller123"
echo ""
