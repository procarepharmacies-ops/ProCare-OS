@echo off
REM ProCare OS - Kill stray/zombie backend processes (run as Administrator)
REM Some backend python.exe processes end up elevated and survive normal kills,
REM holding port 8000 and running an old sync. This clears them all.
REM
REM Right-click this file -> "Run as administrator".

echo Killing all python.exe backend processes...
taskkill /F /IM python.exe /T 2>nul

echo.
echo Checking port 8000...
netstat -ano | findstr ":8000" | findstr LISTENING
if %ERRORLEVEL% EQU 0 (
    echo   Port 8000 still held - a process may need manual End Task in Task Manager.
) else (
    echo   Port 8000 is now FREE.
)

echo.
echo Done. Tell Claude "done" so it can finish the branch cleanup and
echo restart a clean backend on port 8000.
echo.
pause
