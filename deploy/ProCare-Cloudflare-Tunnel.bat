@echo off
rem ============================================================================
rem  ProCare - PUBLISH ON THE INTERNET VIA A CLOUDFLARE TUNNEL (Windows).
rem
rem  Opens the pharmacy system to the public internet so it can be reached from
rem  a phone anywhere. That is a one-way door, so this script REFUSES to run
rem  until the box is actually safe to expose:
rem
rem    * AUTH_SECRET must not be the dev default. It HMAC-signs session tokens,
rem      so while it is the default ANYONE can forge a CEO token with no
rem      password. Changing passwords does not help until this is fixed.
rem    * AUTH_ENABLED must be on.
rem    * No account may still use the seeded demo password.
rem
rem  BEFORE running this (one time, in the Cloudflare dashboard):
rem    1. Zero Trust -> Networks -> Tunnels -> create a tunnel, copy its TOKEN.
rem    2. In that tunnel's Public Hostname, add your hostname
rem       (e.g. procare.example.com) with Service = HTTP://localhost:3000
rem
rem  Usage:  ProCare-Cloudflare-Tunnel.bat <TUNNEL_TOKEN>
rem
rem  NOTE: this exposes the ProCare UI only. It must NEVER expose SQL Server -
rem  port 1433 stays LAN-only. The Elsanta instance is SQL Server 2008, which is
rem  end-of-life and unpatched; putting it on the internet would be indefensible.
rem ============================================================================
setlocal enabledelayedexpansion

set ROOT=%USERPROFILE%\ProCare-OS
set FRONTEND_PORT=3000
set TOKEN=%~1

title ProCare - Cloudflare Tunnel

cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)

if "%TOKEN%"=="" (
  echo.
  echo  Missing tunnel token.
  echo    Cloudflare Zero Trust -^> Networks -^> Tunnels -^> ^(your tunnel^) -^> token
  echo  Then run:
  echo    deploy\ProCare-Cloudflare-Tunnel.bat ^<TUNNEL_TOKEN^>
  echo.
  pause & exit /b 1
)

rem ---- 1) Security gate - the whole point of this script ----------------------
echo.
echo [1/4] Checking whether this system is safe to put on the internet...
echo.
cd /d "%ROOT%\src\backend"
python -m app.services.exposure --check
if errorlevel 1 goto unsafe
cd /d "%ROOT%"
echo.
echo   Security check PASSED.

rem ---- 2) Install cloudflared -------------------------------------------------
echo.
echo [2/4] Installing cloudflared...
set CFD=%ROOT%\deploy\cloudflared.exe
if exist "%CFD%" (
  echo   Already present at %CFD%
) else (
  echo   Downloading cloudflared for Windows...
  powershell -NoProfile -Command ^
    "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%CFD%' -UseBasicParsing; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
  if errorlevel 1 (
    echo   Download FAILED. Check internet access, or download it by hand from
    echo     https://github.com/cloudflare/cloudflared/releases/latest
    echo   and save it as %CFD%
    pause & exit /b 1
  )
  echo   Installed to %CFD%
)

rem ---- 3) Register the tunnel as a Windows service ----------------------------
echo.
echo [3/4] Registering the tunnel as an always-on Windows service...
echo       (needs Administrator - if this fails, re-run as Administrator)
"%CFD%" service install %TOKEN%
if errorlevel 1 (
  echo.
  echo   Service install failed. Common causes:
  echo     - this window is not running as Administrator
  echo     - a tunnel service is already installed ^(remove it first:
  echo       "%CFD%" service uninstall^)
  echo   You can also run it in the foreground to test:
  echo     "%CFD%" tunnel --no-autoupdate run --token ^<TOKEN^>
  pause & exit /b 1
)

rem ---- 4) Done ----------------------------------------------------------------
echo.
echo [4/4] Tunnel service installed and running.
echo.
echo ============================================================================
echo  ProCare is now reachable at the hostname you configured in Cloudflare.
echo.
echo  Confirm the tunnel points at:  HTTP://localhost:%FRONTEND_PORT%
echo  ^(Zero Trust -^> Networks -^> Tunnels -^> your tunnel -^> Public Hostname^)
echo.
echo  Keep in mind:
echo    - The login screen is the ONLY thing between the internet and the
echo      pharmacy's data. Do not disable AUTH_ENABLED.
echo    - SQL Server port 1433 must stay LAN-only. Never add it to the tunnel.
echo    - Re-run the security check any time:
echo        python -m app.services.exposure --check
echo.
echo  To stop publishing:   "%CFD%" service uninstall
echo ============================================================================
pause
exit /b 0

:unsafe
echo.
echo ============================================================================
echo  REFUSING TO OPEN THE TUNNEL.
echo.
echo  The blockers listed above must be fixed first. Until then, opening this
echo  to the internet would expose the pharmacy's data, payroll and patient
echo  records to anyone who finds the URL.
echo.
echo  To fix:
echo    AUTH_SECRET   - add a long random value to %ROOT%\.env :
echo                      AUTH_SECRET=^<paste 40+ random characters^>
echo                    Generate one:
echo                      python -c "import secrets; print(secrets.token_urlsafe(48))"
echo    AUTH_ENABLED  - add to %ROOT%\.env :  AUTH_ENABLED=true
echo    Weak accounts - change each named account:
echo                      cd %ROOT%\src\backend
echo                      python -m app.services.exposure --set-password ^<user^> ^<password^>
echo.
echo  Then RESTART ProCare (so .env is re-read) and run this script again.
echo ============================================================================
pause
exit /b 1
