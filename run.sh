#!/bin/bash

echo "Initiating build..."
BUILD_DIR="_site"
# if [ -d "$BUILD_DIR" ]; then
#     echo "Removing $BUILD_DIR"
#     rm -Rf $BUILD_DIR;
#     echo "Done."
# fi
echo "Converting markdown to html..."
python makesite.py

echo "Build complete."
echo "Starting python server..."
cd $BUILD_DIR
python -m http.server
