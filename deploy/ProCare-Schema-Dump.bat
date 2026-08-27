@echo off
REM ProCare Schema Dump — Extract real eStock schema from Elsanta server
REM Usage: Double-click this script from the repo root, or run from CMD

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║      ProCare eStock Schema Dump — Elsanta Server              ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check if config\connections.json exists
if not exist "config\connections.json" (
    echo ❌ config\connections.json NOT FOUND
    echo.
    echo Before running this script, you must:
    echo   1. Run: deploy\ProCare-Connect-eStock.bat
    echo   2. Configure your eStock read-only login in config\connections.json
    echo.
    pause
    exit /b 1
)

echo ✓ Found config\connections.json
echo.

REM Check if we're in the repo root (where src/backend exists)
if not exist "src\backend" (
    echo ❌ Not in ProCare OS repo root
    echo Please run this script from the repo directory
    pause
    exit /b 1
)

echo Running schema dump (this may take 1-2 minutes)...
echo.

REM Activate the backend venv if it exists, or use python directly
if exist "src\backend\.venv\Scripts\activate.bat" (
    call src\backend\.venv\Scripts\activate.bat
    python -m tools.estock_schema_dump --counts
) else (
    cd src\backend
    python -m tools.estock_schema_dump --counts
    cd ..\..
)

if %errorlevel% neq 0 (
    echo.
    echo ❌ Schema dump failed. Check your eStock connection and try again.
    pause
    exit /b 1
)

echo.
echo ✓ Schema dump complete!
echo.
echo Generated files:
echo   • docs\estock-schema-dump.md (human-readable coverage report)
echo   • docs\estock-schema-dump.json (machine-readable full schema)
echo.
echo Next steps:
echo   1. Review docs\estock-schema-dump.md in Notepad
echo   2. Commit both files to git
echo   3. Send to the dev team for PR 2e (GL sub-ledger mirrors)
echo.

REM Offer to open report
set /p open_report="Open report in Notepad? (Y/n): "
if /i "%open_report%"=="y" (
    start notepad docs\estock-schema-dump.md
)

echo.
pause
exit /b 0
