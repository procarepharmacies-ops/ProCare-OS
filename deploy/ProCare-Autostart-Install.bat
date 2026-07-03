@echo off
rem ============================================================================
rem  ProCare AI — one-time installer for the desktop icon + autostart.
rem
rem  Run this ONCE (double-click). It:
rem   1. Puts a "ProCare AI" icon on your Desktop (one click opens the system).
rem   2. Makes the ProCare server start automatically with Windows and stay on
rem      in the background, so http://localhost:3000 is ALWAYS available.
rem
rem  To undo: delete "ProCare AI" from the Desktop and from
rem  shell:startup (Win+R, type shell:startup, Enter).
rem
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
set ROOT=%USERPROFILE%\ProCare-OS
set LAUNCHER=%ROOT%\deploy\ProCare-Local.bat
set ICON=%ROOT%\src\frontend\public\procare.ico

if not exist "%LAUNCHER%" (echo ProCare not found at %ROOT% & pause & exit /b 1)

echo [1/2] Creating the Desktop icon...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\ProCare AI.lnk');" ^
  "$s.TargetPath = '%LAUNCHER%';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.IconLocation = '%ICON%';" ^
  "$s.Description = 'ProCare AI - pharmacy operating system';" ^
  "$s.Save()"

echo [2/2] Installing autostart (server starts with Windows, no browser)...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\ProCare Server.lnk');" ^
  "$s.TargetPath = '%LAUNCHER%';" ^
  "$s.Arguments = 'serve';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.IconLocation = '%ICON%';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'ProCare AI server (background autostart)';" ^
  "$s.Save()"

echo.
echo Done!
echo  - Desktop icon "ProCare AI": one click opens the system.
echo  - The server now starts automatically every time Windows starts.
echo  - Starting it right now in the background...
start "" /min "%LAUNCHER%" serve
echo.
pause
