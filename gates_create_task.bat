@echo off
C:\Windows\System32\schtasks.exe /create /tn GateBridgeStartup /tr "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s -d C:\Users\Public\GateBridge.exe" /sc onlogon /ru SYSTEM /rl highest /f > C:\Users\Public\gate_task.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\gate_task.log
