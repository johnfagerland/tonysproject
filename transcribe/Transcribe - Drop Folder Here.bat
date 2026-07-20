@echo off
rem Drag a FOLDER of interview clips onto this file to transcribe everything in it.
setlocal
if "%~1"=="" (
    echo.
    echo   Drag a folder of video files onto this .bat file to transcribe them.
    echo   ^(Don't double-click it - drag a folder onto it.^)
    echo.
    pause
    exit /b 1
)
cd /d "%~dp0"
python transcribe.py "%~1"
echo.
echo ============================================
echo Finished. Transcripts are in a "transcripts"
echo folder inside the folder you dropped.
echo ============================================
pause
