@echo off
rem ProCare AI — Windows desktop launcher.
rem
rem SETUP (one time): copy this file to your Windows Desktop.
rem Optional: right-click > Properties > Change Icon, and pick the ProCare
rem logo (save src\frontend\public\logo.png as .ico first, e.g. via any
rem online png-to-ico converter).
rem
rem Double-click = makes sure the server is running, then opens ProCare.
rem If your ProCare folder in WSL is not ~/ProCare-OS, edit the path below.

title ProCare AI
echo Starting ProCare AI ... please wait
wsl bash -lc "cd ~/ProCare-OS && ./deploy/procare.sh start"
start "" http://localhost:3000
exit
