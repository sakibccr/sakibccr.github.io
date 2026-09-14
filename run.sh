#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

echo "Initiating build..."
BUILD_DIR="_site"
echo "Converting markdown to html..."
python makesite.py

echo "Build complete."
echo "Starting python server..."
python -m http.server --bind 127.0.0.1 --directory "$BUILD_DIR" 8000
