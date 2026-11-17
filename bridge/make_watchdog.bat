@echo off
C:\Windows\System32\schtasks.exe /create /tn GateBridgeWatchdog /tr "C:\Users\Public\bridge_watchdog.bat" /sc minute /mo 5 /ru SYSTEM /rl highest /f > C:\Users\Public\watchdog_task.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\watchdog_task.log
C:\Windows\System32\schtasks.exe /run /tn GateBridgeWatchdog >> C:\Users\Public\watchdog_task.log 2>&1
echo run_rc=%ERRORLEVEL% >> C:\Users\Public\watchdog_task.log
