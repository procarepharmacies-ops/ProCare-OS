@echo off
rem ============================================================================
rem  ProCare - SEED THE ELSANTA BRANCH FROM A RESTORED eStock BACKUP.
rem
rem  Runs the whole seeding runbook in order, stopping at the first failure:
rem    1. Tests the read-only eStock connection.
rem    2. BACKS UP ProCare and verifies the backup (a backup nobody verified
rem       is not a backup).
rem    3. INSPECTS ProCare and decides whether a full import is actually due.
rem       This is the step that saves the afternoon: the mirror can only sync
rem       incrementally once the branch ALREADY holds sales, so on an empty
rem       branch every "quick sync" is silently a full load anyway.
rem    4. Runs the full import ONLY if step 3 says it is needed, and only
rem       after you confirm.
rem    5. Repoints config to the LIVE eStock database.
rem    6. Enables continuous background sync in .env.
rem
rem  BEFORE running this (once, in SSMS):
rem    - Restore the eStock .bak beside the live DB under its own name
rem      (default below: stock_seed).  See deploy\SQL-SERVER-2008-ELSANTA.md
rem    - Fill config\connections.json -> estock_source + procare_database
rem
rem  Safe to re-run: it re-checks state every time and never imports twice
rem  without asking.
rem ============================================================================
setlocal enabledelayedexpansion

set ROOT=%USERPROFILE%\ProCare-OS
set SEED_DB=stock_seed
set BRANCH=ELSANTA
set LIVE_DB=stock

rem Smaller chunks = smaller RAM spikes during the import. The default (20000)
rem can push a modest branch PC into swap, which looks exactly like a hang.
set SYNC_CHUNK_ROWS=5000

title ProCare - Seed %BRANCH%

cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)
if not exist "config\connections.json" (
  echo config\connections.json is missing. Copy config\connections.example.json
  echo to config\connections.json and fill in the SQL logins first.
  pause & exit /b 1
)

for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set TODAY=%%d-%%c-%%b
set BAKFILE=F:\backup\ProCare_before_sync_%TODAY%.bak

echo.
echo ============================================================================
echo  ProCare - seeding branch %BRANCH% from database %SEED_DB%
echo  Backup will be written to: %BAKFILE%
echo ============================================================================

rem ---- 1) Read-only preflight -------------------------------------------------
echo.
echo [1/6] Testing the eStock connection (read-only check)...
cd /d "%ROOT%\src\backend"
python -m app.services.etl --check
if errorlevel 1 goto check_failed
echo.
echo   Confirm above:  "ok": true  AND  "read_only": true
choice /c YN /m "Does it say ok:true and read_only:true (Y/N)"
if errorlevel 2 goto check_failed

rem ---- 2) Back up ProCare -----------------------------------------------------
echo.
echo [2/6] Backing up ProCare and verifying the backup...
echo       (this can take a minute)
python -m app.services.seeding --backup "%BAKFILE%"
if errorlevel 1 goto backup_failed
echo.
echo   Backup written and verified: %BAKFILE%

rem ---- 3) Decide whether an import is due -------------------------------------
echo.
echo [3/6] Inspecting ProCare to see whether a full import is needed...
python -m app.services.seeding --inspect %BRANCH%
if errorlevel 2 goto do_import
if errorlevel 1 goto inspect_failed

echo.
echo   %BRANCH% is ALREADY seeded - skipping the import entirely.
goto repoint

rem ---- 4) Full import (only when step 3 says so) ------------------------------
:do_import
echo.
echo [4/6] %BRANCH% has no mirrored sales, so a FULL import is required.
echo.
echo   This REPLACES ProCare's current data with the data from %SEED_DB%.
echo   Your verified backup is at: %BAKFILE%
echo.
echo   It prints NOTHING until it finishes - that is normal, the whole import
echo   is one transaction. Do NOT close this window. Expect 10-40 minutes.
echo.
echo   To watch it work, open SSMS in another window and re-run:
echo     USE ProCare; SELECT COUNT(*) FROM sales;
echo.
choice /c YN /m "Run the full import now (Y/N)"
if errorlevel 2 (echo Stopped. Nothing was imported. & pause & exit /b 0)

echo.
echo   Importing... (started at %TIME%)
python -m app.services.etl --import %SEED_DB% %BRANCH% --fresh
if errorlevel 1 goto import_failed
echo.
echo   Import finished at %TIME%. Row counts are above.

rem ---- 5) Repoint at the live database ----------------------------------------
:repoint
echo.
echo [5/6] Point ProCare at the LIVE eStock database ("%LIVE_DB%")?
echo       Notepad will open config\connections.json - change
echo         "database": "%SEED_DB%"   to   "database": "%LIVE_DB%"
echo       in the estock_source block, save, and close Notepad.
choice /c YN /m "Open the config to repoint now (Y/N)"
if errorlevel 2 goto autosync
start /wait notepad "%ROOT%\config\connections.json"
echo.
echo   Re-testing against the live database...
python -m app.services.etl --check
if errorlevel 1 (echo   Live check FAILED - fix the config and re-run this file. & pause & exit /b 1)
echo.
echo   Confirm above:  "read_only": true   ^(ProCare must never write to eStock^)

rem ---- 6) Continuous background sync ------------------------------------------
:autosync
cd /d "%ROOT%"
echo.
choice /c YN /m "[6/6] Enable continuous background sync (Y/N)"
if errorlevel 2 goto finish
findstr /b /c:"SYNC_ENABLED" ".env" >nul 2>nul
if errorlevel 1 (
  echo SYNC_ENABLED=1>> ".env"
  echo SYNC_INTERVAL_SECONDS=30>> ".env"
  echo SYNC_INCREMENTAL_DAYS=7>> ".env"
  echo SYNC_CHUNK_ROWS=5000>> ".env"
  echo   Added the sync settings to .env
) else (
  echo   SYNC_ENABLED already set in .env - leaving it as is.
)

:finish
echo.
echo ============================================================================
echo  DONE. Restart ProCare, then check:
echo    http://localhost:8100/api/health        -^> "procare_db": "sqlserver"
echo    http://localhost:8100/api/sync/status   -^> "running": true
echo.
echo  Your pre-seed backup is kept at:
echo    %BAKFILE%
echo  Drop the seed database (DROP DATABASE %SEED_DB%) only once the
echo  dashboard shows real pharmacy numbers.
echo ============================================================================
pause
exit /b 0

rem ---- failure paths ----------------------------------------------------------
:check_failed
echo.
echo  CONNECTION CHECK FAILED. Check that:
echo   - config\connections.json estock_source has the real read-only login
echo   - "database" is set to %SEED_DB% and that database exists in SSMS
echo   - the ODBC driver in the config matches one from: Get-OdbcDriver
echo     (on SQL Server 2008 this is usually "SQL Server Native Client 10.0")
pause & exit /b 1

:backup_failed
echo.
echo  BACKUP FAILED - nothing else was attempted, ProCare is untouched.
echo  Check that:
echo   - F:\backup exists and has free space
echo   - the procare_database login in connections.json can back up ProCare
echo   - you are NOT using WITH COMPRESSION (Enterprise-only on SQL 2008)
pause & exit /b 1

:inspect_failed
echo.
echo  INSPECT FAILED - could not read ProCare. Nothing was imported.
echo  Check the procare_database block in config\connections.json.
pause & exit /b 1

:import_failed
echo.
echo  IMPORT FAILED. ProCare was NOT left half-imported - the whole import is
echo  one transaction, so SQL Server rolled it back, including the wipe.
echo  Your verified backup is still at:
echo    %BAKFILE%
echo  Send the error text above for diagnosis.
pause & exit /b 1
