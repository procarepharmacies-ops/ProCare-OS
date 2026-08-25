@echo off
rem ============================================================================
rem  ProCare - DUMP THE eStock SCHEMA (one double-click).
rem
rem  Runs the read-only schema-inspection tool (tools\estock_schema_dump.py)
rem  against the eStock login already configured in config\connections.json,
rem  and writes two files at the repo root:
rem    docs\estock-schema-dump.md    - human-readable report (every table +
rem                                    columns + row counts + a coverage-gap
rem                                    section: which tables ProCare's ETL
rem                                    does NOT yet read)
rem    docs\estock-schema-dump.json  - the same data, machine-readable
rem
rem  STRICTLY READ-ONLY: it only inspects table/column metadata and runs
rem  COUNT(*) per table. It NEVER writes to eStock. Safe to re-run any time -
rem  each run overwrites the previous report with the current schema.
rem
rem  BEFORE running this:
rem    - config\connections.json must exist with a real eStock login filled
rem      in (run ProCare-Connect-eStock.bat first if you haven't already).
rem
rem  AFTER it finishes:
rem    - Send docs\estock-schema-dump.md (or the whole repo, if you commit
rem      it) back for the next mirror to be built against the real columns.
rem
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
setlocal enabledelayedexpansion
set ROOT=%USERPROFILE%\ProCare-OS

title ProCare - eStock Schema Dump
cd /d "%ROOT%" || (echo ProCare folder not found at %ROOT% & pause & exit /b 1)
where python >nul 2>nul || (echo Python is not installed or not on PATH & pause & exit /b 1)

if not exist "config\connections.json" (
  echo config\connections.json is missing - no eStock login is configured yet.
  echo Run ProCare-Connect-eStock.bat first, then come back and run this.
  pause & exit /b 1
)

echo.
echo ============================================================================
echo  ProCare - eStock schema dump (read-only; --counts also runs COUNT(*))
echo ============================================================================
echo.
echo This inspects every table in the eStock database and its columns, and
echo counts rows in each one. On a full production database this can take a
echo few minutes - it never writes anything to eStock.
echo.

rem The tools\ package lives at the repo root, not under src\backend - the
rem module must run from here for `python -m tools.estock_schema_dump` to
rem find it (app.* imports still resolve via the script's own sys.path shim).
python -m tools.estock_schema_dump --counts
if errorlevel 1 goto dump_failed

if not exist "docs\estock-schema-dump.md" goto dump_failed

echo.
echo ============================================================================
echo  DONE. Wrote:
echo    docs\estock-schema-dump.md
echo    docs\estock-schema-dump.json
echo ============================================================================
echo.
choice /c YN /m "Open the report in Notepad now (Y/N)"
if not errorlevel 2 start notepad "docs\estock-schema-dump.md"
echo.
echo Next step: send these two files back (or commit + push them on a branch)
echo so the next eStock mirror can be built against the real column names
echo instead of guesses.
echo.
pause
exit /b 0

:dump_failed
echo.
echo  SCHEMA DUMP FAILED. Check that:
echo   - config\connections.json estock_source has the real (non-placeholder)
echo     login - the tool refuses to run against the example/template values
echo   - the ODBC driver named in the config is actually installed
echo     (on SQL Server 2008 this is usually "SQL Server Native Client 10.0")
echo   - the eStock server is reachable from this PC
echo Send the error text above for diagnosis.
pause
exit /b 1
