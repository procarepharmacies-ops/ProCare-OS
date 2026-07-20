@echo off
rem ============================================================================
rem  ProCare AI - CONNECT THE REAL eStock DATABASE (one double-click).
rem
rem  What it does, step by step, with a confirmation before anything changes:
rem   1. Creates config\connections.json from the template if it doesn't exist
rem      and opens it in Notepad so you fill the eStock read-only login
rem      (the "estock_source" block: server / database / username / password).
rem   2. TESTS the connection (also verifies the login truly cannot write).
rem   3. Asks, then runs the FULL SYNC: products, customers, vendors, stock,
rem      sales, purchases  ->  ProCare's own database.
rem      NOTE: this REPLACES ProCare's current (demo) data with the real data.
rem   4. Asks, then enables continuous background sync (SYNC_ENABLED=1 in .env).
rem
rem  Run it again any time - safe to repeat.
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
setlocal enabledelayedexpansion
set ROOT=%USERPROFILE%\ProCare-OS

title ProCare - Connect eStock
cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)

rem ---- 1) Config file ---------------------------------------------------------
if not exist "config\connections.json" (
  echo [1/4] Creating config\connections.json from the template...
  copy /y "config\connections.example.json" "config\connections.json" >nul
  echo.
  echo   Notepad will open now. In the "estock_source" block fill in:
  echo     "username": the READ-ONLY SQL Server login
  echo     "password": its password
  echo   ^(server 192.168.1.2 / database "stock" are already set^)
  echo   Save the file and CLOSE Notepad to continue.
  echo.
  pause
  start /wait notepad "config\connections.json"
) else (
  echo [1/4] config\connections.json already exists - using it.
)

rem ---- 2) Test the connection -------------------------------------------------
echo.
echo [2/4] Testing the eStock connection (read-only check)...
cd src\backend
python -m app.services.etl --check
if errorlevel 1 (echo Python failed to run the check. & pause & exit /b 1)
echo.
echo   If you see  "ok": true   above, the connection works.
echo   If you see  "ok": false  fix the login in config\connections.json
echo   and run this file again.
echo.
choice /c YN /m "Did the check say ok: true? Continue to the FULL SYNC (Y/N)"
if errorlevel 2 (echo Stopped. Nothing was changed. & pause & exit /b 0)

rem ---- 3) Full sync -----------------------------------------------------------
echo.
echo [3/4] Running the full sync - this REPLACES ProCare's current (demo) data
echo        with the real eStock data. It can take a few minutes...
choice /c YN /m "Run the full sync now (Y/N)"
if errorlevel 2 (echo Skipped the sync. & goto autosync)
python -m app.services.etl --run
echo.
echo   Done. The row counts above are what was imported.

:autosync
rem ---- 4) Continuous background sync ------------------------------------------
cd /d "%ROOT%"
echo.
choice /c YN /m "[4/4] Keep syncing automatically in the background (Y/N)"
if errorlevel 2 goto finish
findstr /b /c:"SYNC_ENABLED" ".env" >nul 2>nul
if errorlevel 1 (
  echo SYNC_ENABLED=1>> ".env"
  echo   Added SYNC_ENABLED=1 to .env
) else (
  echo   SYNC_ENABLED already set in .env - leaving it as is.
)

:finish
echo.
echo All set. RESTART ProCare now (close the two ProCare windows and
echo double-click the ProCare desktop icon) - the dashboard will show
echo the real pharmacy numbers.
echo.
pause
