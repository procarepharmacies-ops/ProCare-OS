@echo off
REM ProCare OS - Start SQL Server (run as Administrator)
REM Right-click this file and choose "Run as administrator"

echo Starting SQL Server (MSSQLSERVER default instance)...
net start MSSQLSERVER

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: SQL Server is now running on localhost
    echo Setting service to start automatically on boot...
    sc config MSSQLSERVER start= auto >nul
    echo.
    echo Done. You can close this window and continue.
) else (
    echo.
    echo FAILED to start SQL Server. Error code: %ERRORLEVEL%
    echo Make sure you ran this file as Administrator.
)

echo.
pause
