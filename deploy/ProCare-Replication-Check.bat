@echo off
rem ============================================================================
rem  ProCare - REPLICATION CHECK (READ-ONLY). Run once on EACH branch PC:
rem
rem      deploy\ProCare-Replication-Check.bat elsanta
rem      deploy\ProCare-Replication-Check.bat mashala
rem
rem  Optional SQL login instead of Windows login:
rem      deploy\ProCare-Replication-Check.bat elsanta SQLUSER SQLPASSWORD
rem
rem  It collects, into ONE text file, everything needed to find why eStock
rem  replication between the branches stopped: this PC's IP and PUBLIC IP, whether
rem  the other branch's SQL port answers, and the read-only SQL diagnostics.
rem  It changes NOTHING (SELECT only; no eStock tables are edited).
rem  Send the file ProCare-replication-<site>.txt (in the ProCare folder) back.
rem ============================================================================
setlocal

set SITE=%~1
set SQLUSER=%~2
set SQLPASS=%~3
set ROOT=%~dp0..
set OUT=%ROOT%\ProCare-replication-%SITE%.txt

if /i "%SITE%"=="elsanta" goto site_elsanta
if /i "%SITE%"=="mashala" goto site_mashala
echo Usage: deploy\ProCare-Replication-Check.bat ^<elsanta^|mashala^> [sqluser sqlpassword]
exit /b 1

:site_elsanta
set SQLFILE=diagnose-replication-elsanta.sql
set PEER=196.202.93.36
set PEERNAME=Mashala
goto start

:site_mashala
set SQLFILE=diagnose-replication-mashala.sql
set PEER=196.202.93.37
set PEERNAME=Elsanta
goto start

:start
title ProCare - Replication check (%SITE%)
echo ProCare replication check for %SITE%  -  read-only.
echo Output file: %OUT%
echo.

echo ===== ProCare replication check: %SITE% ===== > "%OUT%"
echo Date/time: %date% %time% >> "%OUT%"
echo Computer: %COMPUTERNAME% >> "%OUT%"
echo. >> "%OUT%"

echo [1/4] This PC's addresses...
echo ---- Local IPv4 addresses ---- >> "%OUT%"
ipconfig | findstr /i "IPv4" >> "%OUT%"
echo. >> "%OUT%"

echo [2/4] Public IP (the IP the other branch must connect to)...
echo ---- Public IP seen from the internet (expected: Elsanta 196.202.93.37, Mashala 196.202.93.36) ---- >> "%OUT%"
powershell -NoProfile -Command "try { (New-Object Net.WebClient).DownloadString('https://api.ipify.org') } catch { 'FAILED: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo [3/4] Can this PC reach %PEERNAME% (%PEER%) on SQL port 1433?
echo ---- TCP test to %PEERNAME% %PEER%:1433 ---- >> "%OUT%"
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $a = $c.BeginConnect('%PEER%', 1433, $null, $null); if ($a.AsyncWaitHandle.WaitOne(5000, $false) -and $c.Connected) { 'OPEN - the port answers' } else { 'CLOSED or timed out - blocked, wrong IP, or the other server is off' }; $c.Close() } catch { 'ERROR: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo [4/4] Read-only SQL diagnostics (database stock)...
set SQLCMDEXE=
where sqlcmd >nul 2>nul && set SQLCMDEXE=sqlcmd
if not defined SQLCMDEXE where osql >nul 2>nul && set SQLCMDEXE=osql
if not defined SQLCMDEXE goto nosql

set AUTH=-E
if not "%SQLUSER%"=="" set AUTH=-U %SQLUSER% -P %SQLPASS%

echo ---- SQL diagnostics: %SQLFILE% ---- >> "%OUT%"
%SQLCMDEXE% -S . %AUTH% -i "%ROOT%\sql\%SQLFILE%" >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ---- SQL diagnostics: diagnose-capacity.sql (errors about ProCare are normal on a server without it) ---- >> "%OUT%"
%SQLCMDEXE% -S . %AUTH% -i "%ROOT%\sql\diagnose-capacity.sql" >> "%OUT%" 2>&1
goto done

:nosql
echo sqlcmd/osql NOT FOUND - SQL part skipped. >> "%OUT%"
echo.
echo   sqlcmd was not found. The network part was saved. Run the SQL file by hand in
echo   SSMS:  sql\%SQLFILE%   and send those results as well.

:done
echo.
echo ============================================================================
echo  Finished. Nothing was changed.
echo  Send this file back:  %OUT%
echo ============================================================================
pause
exit /b 0
