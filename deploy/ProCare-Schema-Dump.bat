@echo off
rem ============================================================================
rem  ProCare AI - DUMP THE eStock SCHEMA (complete database structure).
rem
rem  What it does:
rem   1. Connects to the eStock database (using the same config as the sync)
rem   2. Reads every table, column, and row count (metadata only - READ-ONLY)
rem   3. Flags which tables ProCare currently mirrors and which are unused
rem   4. Saves the report to docs/estock-schema-dump.md + .json
rem   5. Opens the report so you can review the coverage
rem
rem  Use this to:
rem   - See the complete structure of the eStock database (113+ tables)
rem   - Understand what ProCare mirrors vs what's not yet implemented
rem   - Help prioritize new mirror candidates
rem
rem  Run it any time - it's completely read-only (never writes to eStock).
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
setlocal enabledelayedexpansion
set ROOT=%USERPROFILE%\ProCare-OS

title ProCare - eStock Schema Dump
cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)

rem ---- 1) Check config --------------------------------------------------------
echo.
echo [1/3] Checking eStock configuration...
if not exist "config\connections.json" (
  echo ERROR: config\connections.json not found.
  echo Please run ProCare-Connect-eStock.bat first to set up the connection.
  echo.
  pause
  exit /b 1
)

rem ---- 2) Run the schema dump with row counts --------------------------------
echo.
echo [2/3] Dumping the eStock schema (reading all tables + row counts)...
echo        This may take a minute or two...
python tools\estock_schema_dump.py --counts --out docs\estock-schema-dump.md
if errorlevel 1 (
  echo.
  echo ERROR: The schema dump failed. Check:
  echo   1. Is the eStock database reachable^?
  echo   2. Are the credentials in config\connections.json correct^?
  echo   3. Is the database still running^?
  echo.
  pause
  exit /b 1
)

rem ---- 3) Open the report ----------------------------------------------------
echo.
echo [3/3] Schema dump complete!
echo        The report has been saved to:
echo        docs\estock-schema-dump.md (human-readable)
echo        docs\estock-schema-dump.json (machine-readable)
echo.
choice /c YN /m "Open the report in Notepad now (Y/N)"
if errorlevel 2 goto finish

if exist "docs\estock-schema-dump.md" (
  start /wait notepad "docs\estock-schema-dump.md"
) else (
  echo Report file not found - something went wrong.
  pause
  exit /b 1
)

:finish
echo.
echo Review complete. The schema dump is now available for reference.
echo.
pause
