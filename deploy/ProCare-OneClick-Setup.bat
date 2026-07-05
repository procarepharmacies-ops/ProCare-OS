@echo off
rem ============================================================================
rem  ProCare AI — ONE-CLICK SETUP for a fresh Windows PC.
rem
rem  This is the only file you need to copy to a new machine. Double-click it
rem  and it does EVERYTHING:
rem    1. Installs Git + Python + Node.js automatically (via winget) if missing.
rem    2. Downloads ProCare into  %USERPROFILE%\ProCare-OS  (git clone).
rem       - A private repo opens a GitHub sign-in window once (Git Credential
rem         Manager remembers it afterwards).
rem    3. Creates the "ProCare AI" Desktop icon + Windows autostart, installs
rem       dependencies, builds the app, and starts it.
rem
rem  Already have the ProCare folder? You can double-click
rem  deploy\ProCare-Autostart-Install.bat inside it instead — same result.
rem
rem  Undo: delete "ProCare AI" from the Desktop and from shell:startup.
rem ============================================================================
setlocal enabledelayedexpansion
set ROOT=%USERPROFILE%\ProCare-OS
set REPO_URL=https://github.com/procarepharmacies-ops/ProCare-OS.git

title ProCare AI - One-Click Setup
echo ============================================
echo   ProCare AI - One-Click Setup
echo ============================================
echo.

rem ---- 1) Prerequisites via winget (skips anything already installed) -------
where winget >nul 2>nul || (
  echo winget is not available. Install "App Installer" from the Microsoft
  echo Store, or install Git+Python+Node manually, then run this file again.
  pause & exit /b 1
)

where git >nul 2>nul || (
  echo [setup] installing Git...
  winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
)
where python >nul 2>nul || (
  echo [setup] installing Python 3.12...
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
)
where npm >nul 2>nul || (
  echo [setup] installing Node.js LTS...
  winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
)

rem Fresh installs are not on THIS window's PATH yet - reload it from registry.
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%b"
set "PATH=%SYS_PATH%;%USR_PATH%;%PATH%"

where git >nul 2>nul    || (echo Git install needs a new window - close this and run the file again. & pause & exit /b 1)
where python >nul 2>nul || (echo Python install needs a new window - close this and run the file again. & pause & exit /b 1)
where npm >nul 2>nul    || (echo Node install needs a new window - close this and run the file again. & pause & exit /b 1)

rem ---- 2) Get / update ProCare ----------------------------------------------
if exist "%ROOT%\.git" (
  echo [setup] ProCare already downloaded - pulling the newest version...
  git -C "%ROOT%" pull --ff-only
) else (
  echo [setup] downloading ProCare to %ROOT% ...
  git clone "%REPO_URL%" "%ROOT%" || (echo Download failed - check the internet connection / GitHub sign-in. & pause & exit /b 1)
)

rem ---- 3) Desktop icon + autostart + first start -----------------------------
call "%ROOT%\deploy\ProCare-Autostart-Install.bat"
