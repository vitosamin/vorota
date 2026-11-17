@echo off
set OUT=C:\Users\Public\mkw2.txt
C:\Windows\System32\schtasks.exe /create /tn GateBridgeWatchdog /tr "C:\Users\Public\bridge_watchdog.bat" /sc minute /mo 2 /ru SYSTEM /rl highest /f > "%OUT%" 2>&1
echo rc=%ERRORLEVEL% >> "%OUT%"
C:\Windows\System32\schtasks.exe /query /tn GateBridgeWatchdog /fo LIST >> "%OUT%" 2>&1
