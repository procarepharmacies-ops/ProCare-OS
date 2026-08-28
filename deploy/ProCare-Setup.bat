@echo off
REM ProCare OS Pharmacy PC Setup Script
REM Run this on the pharmacy Windows PC to set up ProCare
REM Requirements: Python 3.11+, Node.js 22+, Git

setlocal enabledelayedexpansion

echo.
echo ============================================
echo  ProCare OS — Pharmacy PC Setup
echo ============================================
echo.

REM Step 1: Check prerequisites
echo Step 1: Checking prerequisites...
python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.11+ from https://www.python.org/
  echo Make sure to check "Add Python to PATH" during installation.
  pause
  exit /b 1
)
echo   ✓ Python found

node --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Node.js not found. Install from https://nodejs.org/
  echo Make sure to install Node 22 or later.
  pause
  exit /b 1
)
echo   ✓ Node.js found

git --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git not found. Install from https://git-scm.com/
  pause
  exit /b 1
)
echo   ✓ Git found

echo.
echo Step 2: Cloning repository...
if exist ProCare-OS (
  echo   ProCare-OS folder exists. Using existing clone.
  cd ProCare-OS
) else (
  git clone https://github.com/procarepharmacies-ops/ProCare-OS.git
  if errorlevel 1 (
    echo ERROR: Failed to clone repository.
    pause
    exit /b 1
  )
  cd ProCare-OS
)
echo   ✓ Repository ready

echo.
echo Step 3: Installing backend dependencies...
cd src\backend
pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Failed to install backend dependencies.
  pause
  exit /b 1
)
echo   ✓ Backend dependencies installed

echo.
echo Step 4: Installing frontend dependencies...
cd ..\frontend
call npm install
if errorlevel 1 (
  echo ERROR: Failed to install frontend dependencies.
  pause
  exit /b 1
)
echo   ✓ Frontend dependencies installed

echo.
echo Step 5: Creating .env configuration file...
cd ..\..
if not exist .env (
  echo Creating default .env...
  (
    echo.
    echo REM ProCare OS Configuration
    echo SYNC_ENABLED=0
    echo SYNC_INTERVAL_SECONDS=30
    echo BRANCH_TIMEZONE=Africa/Cairo
    echo AI_PROVIDER=gemini
    echo PROCARE_API_PORT=8100
    echo PROCARE_RELOAD=0
  ) > .env
  echo   Created .env with defaults. Edit if needed.
) else (
  echo   .env already exists. Skipping.
)

echo.
echo Step 6: Creating eStock connection file...
if not exist config\connections.json (
  mkdir config
  echo {
  echo   "provider": "mssql",
  echo   "server": "^<eStock server IP or hostname^>",
  echo   "database": "^<eStock database name^>",
  echo   "username": "^<read-only login^>",
  echo   "password": "^<password^>"
  echo } > config\connections.json
  echo   Created config\connections.json. EDIT with your eStock credentials!
) else (
  echo   config\connections.json already exists. Skipping.
)

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo NEXT STEPS:
echo.
echo 1. Edit config\connections.json with your eStock read-only login
echo.
echo 2. Edit .env if needed:
echo    - BRANCH_TIMEZONE: Set to your pharmacy's timezone
echo    - AI_PROVIDER: Leave as "gemini" or set to "hermes" (OpenRouter)
echo    - SYNC_ENABLED: Set to 1 for continuous sync (leave 0 for manual)
echo.
echo 3. Test eStock connection:
echo    Run: deploy\ProCare-Connect-eStock.bat
echo.
echo 4. Start the system:
echo    Terminal 1: cd src\backend ^&^& python run.py
echo    Terminal 2: cd src\frontend ^&^& npm run dev
echo    Then open browser: http://localhost:3000
echo.
echo 5. Follow DEPLOYMENT_CHECKLIST.md for smoke tests
echo.
echo Questions? See DEPLOYMENT_CHECKLIST.md or check .local-run\backend.log
echo.

pause
