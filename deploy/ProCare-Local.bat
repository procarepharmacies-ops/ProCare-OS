@echo off
rem ProCare AI — LOCAL Windows launcher (no Docker, no WSL).
rem
rem Runs the system natively: FastAPI backend (SQLite) + Next.js frontend,
rem then opens the browser. First run installs dependencies and builds the
rem frontend (needs internet once); after that it works fully offline.
rem
rem REQUIREMENTS (one-time install): Python 3.11+ and Node.js 18+ from
rem   https://www.python.org/downloads/   https://nodejs.org/
rem
rem SETUP: copy a SHORTCUT of this file to the Desktop. To give it the
rem ProCare icon: right-click the shortcut > Properties > Change Icon >
rem Browse to  src\frontend\public\procare.ico  in this folder.
rem
rem If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
set ROOT=%USERPROFILE%\ProCare-OS

title ProCare AI
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
  echo [setup] building the frontend - one time, please wait...
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

echo Waiting for ProCare to come up...
timeout /t 8 /nobreak >nul
start "" http://localhost:3000
exit
