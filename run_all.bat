@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo Starting processing for files in input...
echo.

python voice_duration_tool.py

echo.
if errorlevel 1 (
    echo Processing finished, but some files failed. See output\all_files_summary.csv
) else (
    echo Processing finished. See the output folder.
)
start "" "%~dp0output"
echo.
pause
