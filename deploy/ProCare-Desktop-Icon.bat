@echo off
rem ============================================================================
rem  ProCare AI - create the DESKTOP ICON (ProCare logo).
rem
rem  Double-click this ONCE. It puts a "ProCare" icon (the ProCare logo) on your
rem  Desktop. From then on, ONE CLICK on that icon starts the backend + the
rem  frontend and opens ProCare in your browser.
rem
rem  This does NOT start a background/always-on server. If you want ProCare to
rem  start automatically every time Windows boots and stay always on, run
rem  deploy\ProCare-Autostart-Install.bat instead (it makes the same icon PLUS
rem  autostart).
rem
rem  If the repo is not at %USERPROFILE%\ProCare-OS, edit the line below.
rem ============================================================================
setlocal
set ROOT=%USERPROFILE%\ProCare-OS
set LAUNCHER=%ROOT%\deploy\ProCare-Local.bat
set ICON=%ROOT%\src\frontend\public\procare.ico

if not exist "%LAUNCHER%" (echo ProCare not found at %ROOT% & pause & exit /b 1)
if not exist "%ICON%" (echo Icon not found at %ICON% & pause & exit /b 1)

echo Creating the "ProCare" Desktop icon (ProCare logo)...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\ProCare.lnk');" ^
  "$s.TargetPath = '%LAUNCHER%';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.IconLocation = '%ICON%,0';" ^
  "$s.Description = 'ProCare AI - one click starts the pharmacy system';" ^
  "$s.Save()"

if errorlevel 1 (echo Could not create the icon. & pause & exit /b 1)

echo.
echo Done! A "ProCare" icon (ProCare logo) is now on your Desktop.
echo One click on it starts the backend + frontend and opens the app.
echo.
pause
