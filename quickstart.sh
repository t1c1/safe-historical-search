#!/usr/bin/env bash
set -euo pipefail

# S-tier quickstart for Inchive
# Usage:
#   ./quickstart.sh [PORT]
# This will use the local ./files folder for your export JSON files.

PORT=${1:-}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Inchive setup..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3.8+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $PYTHON_VERSION"

# Setup virtual environment
echo "📦 Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "📥 Installing dependencies..."
pip install -r requirements.txt >/dev/null 2>&1

# Ensure data and index folders exist
mkdir -p ./files
mkdir -p ./index

DATA_DIR="$(pwd)/files"
echo "📁 Data directory: $DATA_DIR"

# Check for export files
REQUIRED_FILES=("conversations.json" "projects.json" "users.json")
MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$DATA_DIR/$file" ]]; then
    MISSING_FILES+=("$file")
  fi
done

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
  echo "⚠️  Missing export files: ${MISSING_FILES[*]}"
  echo "📂 Copy your Anthropic export files to: $DATA_DIR"
  echo "🔗 If you don't have them yet, get them from: https://claude.ai/settings/data-privacy-controls"
  echo "ℹ️  The app will work with whatever files you have, but search results will be limited."
  echo ""
fi

echo "🔍 Building search index..."
python index.py --export "$DATA_DIR" --out ./index

# External link template is optional and defaults to claude.ai/chat/{conv_id}
: "${CLAUDE_URL_TEMPLATE:=https://claude.ai/chat/{conv_id}}"
export CLAUDE_URL_TEMPLATE

# Choose a port: if not provided, start at 5001 and increment until free
if [[ -z "$PORT" ]]; then
  PORT=5001
fi
while lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; do
  PORT=$((PORT+1))
done

echo ""
echo "🌐 Server starting on http://127.0.0.1:$PORT"
echo "✨ Inchive is ready!"
echo "📖 Press Ctrl+C to stop the server"
echo ""
python server.py --db ./index/chatgpt.db --port "$PORT"
