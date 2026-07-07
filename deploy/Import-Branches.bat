@echo off
REM ===========================================================================
REM  ProCare — fill the new database with the Elsanta + Mashala branch history
REM ===========================================================================
REM  BEFORE running this (once, in SSMS):
REM   1. Restore each backup from D:\old\ into SQL Server Express under its own
REM      name  (see docs/10-historical-backups-mashala-elsanta.md).
REM   2. Put the SQL login in  config\connections.json -> estock_source
REM      (server / username / password). The importer reuses that login.
REM
REM  Then EDIT the two database names below to match what you restored, and
REM  double-click this file. It clears any demo/placeholder data, loads Elsanta,
REM  then APPENDS Mashala — both branches end up in one ProCare database,
REM  sharing one drug catalogue. Run it ONCE.
REM ===========================================================================

set ELSANTA_DB=stock_elsanta
set MASHALA_DB=stock_mashala

cd /d "%~dp0\..\src\backend"

echo.
echo === 1/2  Importing ELSANTA  (from %ELSANTA_DB%) — starting clean ===
python -m app.services.etl --import %ELSANTA_DB% ELSANTA --fresh
if errorlevel 1 goto failed

echo.
echo === 2/2  Importing MASHALA  (from %MASHALA_DB%) — appending ===
python -m app.services.etl --import %MASHALA_DB% MASHALA
if errorlevel 1 goto failed

echo.
echo ===========================================================================
echo  Done. Open ProCare -^> Reports -^> Performance over time -^> By branch
echo  to verify Elsanta and Mashala, then run the audit report.
echo ===========================================================================
pause
exit /b 0

:failed
echo.
echo  IMPORT FAILED. Check that:
echo   - the database names above match what you restored in SSMS
echo   - config\connections.json estock_source has the real SQL login
echo   - the ODBC Driver 18 for SQL Server is installed
pause
exit /b 1
