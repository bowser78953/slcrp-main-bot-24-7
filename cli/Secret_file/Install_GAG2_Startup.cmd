@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~dp0Start_GAG2_Macro.cmd"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Start_GAG2_Macro.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '%TARGET%'; $sc.WorkingDirectory = '%~dp0'; $sc.IconLocation = '%SystemRoot%\System32\SHELL32.dll,1'; $sc.Save()"

if exist "%SHORTCUT%" (
  echo Startup shortcut installed:
  echo %SHORTCUT%
) else (
  echo Failed to install startup shortcut.
  exit /b 1
)

echo.
echo Reboot Windows to test automatic startup.
pause
