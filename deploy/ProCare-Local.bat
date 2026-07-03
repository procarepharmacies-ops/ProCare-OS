@echo off
rem ============================================================================
rem  ProCare AI — ONE-CLICK launcher (no Docker, no WSL).
rem
rem  Double-click = if ProCare is already running it opens instantly;
rem  otherwise it starts the servers first, waits until ready, then opens.
rem
rem  "ProCare-Local.bat serve"  = start the servers only (no browser window).
rem                               Used by the autostart shortcut at Windows boot.
rem
rem  REQUIREMENTS (install once): Python 3.11+  https://www.python.org/downloads/
rem                               Node.js 18+   https://nodejs.org/
rem  ONE-TIME SETUP: run deploy\ProCare-Autostart-Install.bat  — it puts the
rem  ProCare icon on your Desktop and makes the server start with Windows.
rem
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
set ROOT=%USERPROFILE%\ProCare-OS
set MODE=%1

title ProCare AI

rem ---- Fast path: already running? just open it. ----------------------------
powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:3000)|Out-Null;exit 0}catch{exit 1}" >nul 2>nul
if %errorlevel%==0 (
  if /i not "%MODE%"=="serve" start "" http://localhost:3000
  exit /b 0
)

cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)
where npm    >nul 2>nul || (echo Node.js is not installed or not on PATH & pause & exit /b 1)

if not exist ".local-run" mkdir .local-run

if not exist ".local-run\.pip-done" (
  echo [setup] installing backend dependencies...
  python -m pip install -q -r src\backend\requirements.txt && type nul > .local-run\.pip-done
)

if not exist "src\frontend\node_modules" (
  echo [setup] installing frontend dependencies...
  pushd src\frontend
  call npm install --no-audit --no-fund
  popd
)

if not exist ".local-run\.built" (
  echo [setup] building the frontend - one time, please wait a few minutes...
  pushd src\frontend
  rem Both vars must be set at BUILD time - Next bakes the /api proxy rewrite
  rem into the production build manifest.
  set NEXT_PUBLIC_API_BASE=
  set BACKEND_INTERNAL=http://127.0.0.1:8000
  call npm run build && type nul > ..\..\.local-run\.built
  popd
)

echo [start] backend on :8000
start "ProCare backend" /min cmd /c "cd /d %ROOT%\src\backend && set PROCARE_API_PORT=8000&& python run.py > %ROOT%\.local-run\backend.log 2>&1"

echo [start] frontend on :3000
start "ProCare frontend" /min cmd /c "cd /d %ROOT%\src\frontend && set BACKEND_INTERNAL=http://127.0.0.1:8000&& npx next start -p 3000 > %ROOT%\.local-run\frontend.log 2>&1"

rem ---- Wait (up to ~60s) until the UI answers, then open -------------------
echo Waiting for ProCare to come up...
for /l %%i in (1,1,30) do (
  powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:3000)|Out-Null;exit 0}catch{exit 1}" >nul 2>nul
  if not errorlevel 1 goto ready
  timeout /t 2 /nobreak >nul
)
echo ProCare did not start in time — check .local-run\backend.log and frontend.log
pause
exit /b 1

:ready
if /i not "%MODE%"=="serve" start "" http://localhost:3000
exit /b 0
