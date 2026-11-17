@echo off
netstat -an | findstr ":8099" | findstr LISTENING > nul
if %ERRORLEVEL%==0 exit /b 0
echo %DATE% %TIME% restarting bridge >> C:\Users\Public\bridge_watchdog.log
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s -d C:\Users\Public\GateBridge.exe
