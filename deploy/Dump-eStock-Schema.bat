@echo off
REM ===========================================================================
REM  ProCare — capture the live eStock schema (READ-ONLY)
REM ===========================================================================
REM  Run this ONCE on a machine that can reach eStock (the Elsanta branch
REM  server, or any PC with a restored eStock backup). Double-click it.
REM
REM  STRICTLY READ-ONLY. It reads table and column NAMES only (plus row counts
REM  if you ask). It never writes to eStock, never reads patient, sales or
REM  price DATA, and the report it produces contains no records — only the
REM  shape of the database.
REM
REM  WHY THIS MATTERS: three ProCare features are parked waiting on this file:
REM    * the Gedo_* sub-ledger balances (per-customer/vendor/branch balances)
REM    * the EMP_CONTROL permission matrix (~200 undocumented flag columns)
REM    * the remaining "column audit pending" mirrors in etl.py
REM  Their column names are NOT documented anywhere, and guessing them would
REM  silently store real-looking rows with wrong numbers, or grant/deny a
REM  permission that looks authoritative on screen. So they stay unbuilt until
REM  this dump says what the columns actually are.
REM
REM  BEFORE running: config\connections.json must have the read-only eStock
REM  login (the same one the sync uses). If ProCare already syncs, you are set.
REM
REM  AFTER running: commit the two files it writes under docs\ and say so —
REM  that is what unblocks the parked work.
REM ===========================================================================

REM  Must run from the REPO ROOT, not src\backend: there is a second,
REM  unrelated "tools" package under src\backend, and -m tools.estock_schema_dump
REM  would resolve to that one and fail with ModuleNotFoundError.
cd /d "%~dp0\.."

echo.
echo === Dumping eStock schema (read-only) ===
echo     Metadata only. Add --counts yourself for row counts (much slower).
echo.

python -m tools.estock_schema_dump --out docs\estock-schema-dump.md
if errorlevel 1 goto failed

echo.
echo ===========================================================================
echo  Done. Two files were written:
echo     docs\estock-schema-dump.md     (readable report + coverage gap)
echo     docs\estock-schema-dump.json   (machine-readable, used by the build)
echo.
echo  NEXT: commit both files and push, then tell Claude they are in. Neither
echo  contains any pharmacy data - only table and column names.
echo ===========================================================================
pause
exit /b 0

:failed
echo.
echo  DUMP FAILED. Check that:
echo   - config\connections.json estock_source (or estock_sources) has the
echo     real read-only SQL login - the same one the continuous sync uses
echo   - this PC can actually reach the eStock server (the sync works)
echo   - the ODBC Driver 18 for SQL Server is installed
echo   - Python is on PATH (run  python --version  to check)
echo.
echo  You can also point it at a restored backup instead of the live server:
echo     python -m tools.estock_schema_dump --url "mssql+pyodbc://..."
pause
exit /b 1
