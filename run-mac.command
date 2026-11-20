#!/bin/bash
# FirstTrace live desk for macOS: double-click this file (first time: right-click > Open).
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this file again."
  echo "Without Python, open FirstTrace-offline.html in your browser instead."
  read -r -p "Press Enter to close." _
  exit 1
fi
python3 scout.py --serve
read -r -p "FirstTrace stopped. Press Enter to close." _
