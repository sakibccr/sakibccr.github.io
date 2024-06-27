#!/bin/bash

echo "Initiating build..."
rm -r _site
python makesite.py

echo "Build complete."
echo "Starting python server..."
cd _site
python -m http.server
