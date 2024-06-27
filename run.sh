#!/bin/bash

echo "Initiating build..."
rm -r public
python makesite.py

echo "Build complete."
echo "Starting python server..."
cd public
python -m http.server
