@echo off
rem Drag a master file (or a folder of masters) onto this file, then pick a preset.
setlocal
if "%~1"=="" (
    echo.
    echo   Drag a video file ^(or a folder of them^) onto this .bat file.
    echo.
    pause
    exit /b 1
)
cd /d "%~dp0"
python encode.py --list
echo.
set /p PRESET="Type the preset name from the list above: "
python encode.py "%~1" "%PRESET%"
echo.
pause
