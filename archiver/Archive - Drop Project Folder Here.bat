@echo off
rem Drag the FINISHED PROJECT FOLDER onto this file. It will ask which drive to use.
setlocal
if "%~1"=="" (
    echo.
    echo   Drag a project folder onto this .bat file to archive it.
    echo.
    pause
    exit /b 1
)
cd /d "%~dp0"
echo Project to archive: %~1
echo.
set /p DEST="Type the drive letter or folder to archive to (e.g. E:\ ): "
python archiver.py archive "%~1" "%DEST%"
echo.
pause
