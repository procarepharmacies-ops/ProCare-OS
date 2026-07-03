@echo off
rem ============================================================================
rem  ProCare AI — install as a REAL Windows service-style boot task.
rem
rem  Right-click -> "Run as administrator" (needed once).
rem
rem  Compared to ProCare-Autostart-Install.bat (Startup-folder shortcut, needs
rem  a user to log in), this uses Task Scheduler ONSTART as SYSTEM:
rem    * server starts when WINDOWS boots — before anyone logs in;
rem    * keeps running when everyone logs out;
rem    * restarts on failure.
rem
rem  Also (optional) installs the Cloudflare Tunnel as a native Windows
rem  service, so http://localhost:3000 gets a secure PUBLIC https URL — access
rem  ProCare from your phone anywhere, no port forwarding. Paste your tunnel
rem  token when asked (Cloudflare Zero Trust -> Networks -> Tunnels), or press
rem  Enter to skip.
rem
rem  Undo:  schtasks /Delete /TN "ProCare Server" /F
rem         cloudflared service uninstall
rem ============================================================================
setlocal
set ROOT=%USERPROFILE%\ProCare-OS
set LAUNCHER=%ROOT%\deploy\ProCare-Local.bat

net session >nul 2>&1 || (echo Please right-click this file and "Run as administrator". & pause & exit /b 1)
if not exist "%LAUNCHER%" (echo ProCare not found at %ROOT% — edit ROOT in this file. & pause & exit /b 1)

echo [1/3] Installing the boot task (runs as SYSTEM, no login needed)...
schtasks /Create /F /TN "ProCare Server" /SC ONSTART /RU SYSTEM /RL HIGHEST ^
  /TR "cmd /c \"\"%LAUNCHER%\" serve\"" || (echo Failed to create the task. & pause & exit /b 1)

echo [2/3] Starting it now...
schtasks /Run /TN "ProCare Server" >nul

echo [3/3] Cloudflare Tunnel (optional — public https URL for phone access).
set /p TUNNEL_TOKEN="Paste your Cloudflare tunnel token (Enter to skip): "
if "%TUNNEL_TOKEN%"=="" goto done

if not exist "%ProgramFiles%\cloudflared\cloudflared.exe" (
  echo   downloading cloudflared...
  mkdir "%ProgramFiles%\cloudflared" 2>nul
  powershell -NoProfile -Command ^
    "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '$env:ProgramFiles\cloudflared\cloudflared.exe'" ^
    || (echo   download failed — install cloudflared manually and re-run. & pause & exit /b 1)
)
"%ProgramFiles%\cloudflared\cloudflared.exe" service install %TUNNEL_TOKEN% ^
  && echo   Tunnel service installed — it now starts with Windows too. ^
  || echo   Tunnel install failed — check the token and try again.

:done
echo.
echo Done!
echo  - ProCare now starts with WINDOWS BOOT (no login required) and stays on.
echo  - Local:  http://localhost:3000   LAN: http://THIS-PC-IP:3000
echo  - Manage: Task Scheduler -^> "ProCare Server"  (or schtasks /Run /TN "ProCare Server")
echo  - NOTE: run deploy\ProCare-Local.bat once normally first, so Python/Node
echo    dependencies and the UI build exist before the boot task fires.
echo.
pause
