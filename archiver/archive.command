#!/bin/bash
# Mac wrapper: double-click, then follow the prompts.
cd "$(dirname "$0")"
echo "Drag the finished PROJECT FOLDER into this window and press Return:"
read -r PROJECT
PROJECT=$(echo "$PROJECT" | sed "s/^'//;s/'$//" | sed 's/\\ / /g')
echo "Drag the DESTINATION DRIVE (under /Volumes) into this window and press Return:"
read -r DEST
DEST=$(echo "$DEST" | sed "s/^'//;s/'$//" | sed 's/\\ / /g')
python3 archiver.py archive "$PROJECT" "$DEST"
read -p "Press Return to close..."
