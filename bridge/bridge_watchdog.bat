@echo off
set LOG=C:\Users\Public\bridge_watchdog.log
netstat -an | findstr ":8099" | findstr LISTENING > nul
if %ERRORLEVEL%==0 goto gateserv
echo %DATE% %TIME% restarting bridge >> "%LOG%"
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s -d C:\Users\Public\GateBridge.exe
:gateserv
tasklist /fi "imagename eq GateServ.exe" | findstr /i "GateServ" > nul
if %ERRORLEVEL%==0 goto gaterm
echo %DATE% %TIME% starting GateServ >> "%LOG%"
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u "ALM\skudnew" -p "Admin910327" -d "C:\GATE\Server\GateServ.exe"
:gaterm
tasklist /fi "imagename eq GateTerm.exe" | findstr /i "GateTerm" > nul
if %ERRORLEVEL%==0 goto done
echo %DATE% %TIME% starting GateTerm >> "%LOG%"
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u "ALM\skudnew" -p "Admin910327" -d "C:\GATE\Terminal\GateTerm.exe"
:done
exit /b 0
