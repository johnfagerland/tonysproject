#!/bin/bash
# Mac wrapper: double-click, then drag a folder into the Terminal window when prompted,
# or run:  ./transcribe.command /path/to/folder
cd "$(dirname "$0")"
if [ -z "$1" ]; then
    echo "Drag the folder of clips into this window and press Return:"
    read -r FOLDER
else
    FOLDER="$1"
fi
# Strip surrounding quotes/backslashes Terminal adds when you drag a path in
FOLDER=$(echo "$FOLDER" | sed "s/^'//;s/'$//" | sed 's/\\ / /g')
python3 transcribe.py "$FOLDER"
echo
echo "Finished. Transcripts are in a 'transcripts' folder inside that folder."
read -p "Press Return to close..."
