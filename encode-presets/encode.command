#!/bin/bash
# Mac wrapper: double-click, then follow the prompts.
cd "$(dirname "$0")"
python3 encode.py --list
echo
echo "Drag the master file (or a folder of masters) into this window and press Return:"
read -r SOURCE
SOURCE=$(echo "$SOURCE" | sed "s/^'//;s/'$//" | sed 's/\\ / /g')
echo "Type the preset name from the list above:"
read -r PRESET
python3 encode.py "$SOURCE" "$PRESET"
read -p "Press Return to close..."
