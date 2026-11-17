@echo off
set OUT=C:\Users\Public\restart_serv.txt
echo === было === > "%OUT%"
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
echo === останавливаю === >> "%OUT%"
taskkill /IM GateServ.exe /F >> "%OUT%" 2>&1
timeout /t 3 /nobreak > nul
echo === запускаю === >> "%OUT%"
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u "ALM\skudnew" -p "Admin910327" -w "C:\GATE\Server" -d "C:\GATE\Server\GateServ.exe" >> "%OUT%" 2>&1
timeout /t 15 /nobreak > nul
echo === стало === >> "%OUT%"
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateTerm.exe" >> "%OUT%" 2>&1
