@echo off
REM ============================================================================
REM  ProCare OS - health watchdog (auto-restart on failure) - Windows PC
REM
REM  Polls /api/health; after N consecutive failures it restarts the stack so a
REM  frozen backend self-heals instead of waiting for an IT call at 10am.
REM
REM  Usage:
REM    deploy\procare-watchdog.bat          run forever (poll every INTERVAL s)
REM    deploy\procare-watchdog.bat once     one check; exit 0 healthy / 1 unhealthy
REM
REM  Run at logon via Task Scheduler (see deploy\DEPLOYMENT.md).
REM
REM  Config via environment (defaults in parentheses):
REM    HEALTH_URL         (http://localhost:7000/api/health)
REM    INTERVAL           seconds between polls (60)
REM    FAIL_THRESHOLD     consecutive fails before restart (3)
REM    REQUIRE_SQLSERVER  1 = a 200 not on sqlserver counts as failure (1)
REM    COOLDOWN           seconds to wait after a restart (120)
REM    LOG_FILE           log path (%~dp0..\.local-run\watchdog.log)
REM ============================================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

if "%HEALTH_URL%"=="" set "HEALTH_URL=http://localhost:7000/api/health"
if "%INTERVAL%"=="" set "INTERVAL=60"
if "%FAIL_THRESHOLD%"=="" set "FAIL_THRESHOLD=3"
if "%REQUIRE_SQLSERVER%"=="" set "REQUIRE_SQLSERVER=1"
if "%COOLDOWN%"=="" set "COOLDOWN=120"
if "%LOG_FILE%"=="" set "LOG_FILE=%REPO_ROOT%\.local-run\watchdog.log"

if not exist "%REPO_ROOT%\.local-run" mkdir "%REPO_ROOT%\.local-run" 2>nul

REM --- single-check mode -------------------------------------------------------
if /I "%~1"=="once" goto :once
if /I "%~1"=="--once" goto :once

call :log "watchdog started - url=%HEALTH_URL% interval=%INTERVAL%s threshold=%FAIL_THRESHOLD% require_sqlserver=%REQUIRE_SQLSERVER%"
set /a fails=0

:loop
call :check_health
if "%HEALTHY%"=="1" (
  if not "%fails%"=="0" call :log "RECOVERED: health OK after %fails% failure(s)."
  set /a fails=0
) else (
  set /a fails+=1
  call :log "UNHEALTHY: %HEALTH_URL% (consecutive failures: !fails!/%FAIL_THRESHOLD%)."
  if !fails! GEQ %FAIL_THRESHOLD% (
    call :do_restart
    set /a fails=0
    timeout /t %COOLDOWN% /nobreak >nul
    goto :loop
  )
)
timeout /t %INTERVAL% /nobreak >nul
goto :loop

REM --- helpers -----------------------------------------------------------------
:check_health
REM Sets HEALTHY=1 (healthy) or HEALTHY=0 (unhealthy).
set "HEALTHY=0"
set "BODY_FILE=%TEMP%\procare_health_%RANDOM%.txt"
curl -sf -m 10 "%HEALTH_URL%" > "%BODY_FILE%" 2>nul
if errorlevel 1 (
  del "%BODY_FILE%" 2>nul
  exit /b 0
)
if "%REQUIRE_SQLSERVER%"=="1" (
  findstr /C:"sqlserver" "%BODY_FILE%" >nul 2>nul
  if errorlevel 1 (
    del "%BODY_FILE%" 2>nul
    exit /b 0
  )
)
del "%BODY_FILE%" 2>nul
set "HEALTHY=1"
exit /b 0

:do_restart
call :log "RESTART: docker compose restart (in %REPO_ROOT%)"
pushd "%REPO_ROOT%"
docker compose restart >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :log "RESTART: command failed - check the stack manually."
) else (
  call :log "RESTART: completed."
)
popd
exit /b 0

:log
echo %DATE% %TIME%  %~1
echo %DATE% %TIME%  %~1>> "%LOG_FILE%"
exit /b 0

:once
call :check_health
if "%HEALTHY%"=="1" (
  call :log "OK (once): %HEALTH_URL% healthy."
  endlocal
  exit /b 0
)
call :log "FAIL (once): %HEALTH_URL% unhealthy."
endlocal
exit /b 1
