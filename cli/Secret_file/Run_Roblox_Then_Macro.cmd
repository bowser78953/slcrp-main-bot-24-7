@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js is not installed or not in PATH.
  echo Install Node.js from https://nodejs.org and try again.
  pause
  exit /b 1
)

echo Opening Roblox...
start "" "roblox://"

echo.
echo Join your game, then press any key to start the macro panel.
pause >nul

echo Starting Grow a Garden 2 Macro...
node "%~dp0Secrect_file_GAG2.js"

echo.
echo Macro stopped.
pause
