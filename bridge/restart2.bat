@echo off
taskkill /IM GateServ.exe /F > nul 2>&1
timeout /t 3 /nobreak > nul
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u "ALM\skudnew" -p "Admin910327" -w "C:\GATE\Server" -d "C:\GATE\Server\GateServ.exe" > nul 2>&1
timeout /t 15 /nobreak > nul
tasklist /fi "imagename eq GateServ.exe" > C:\Users\Public\srv2.txt 2>&1
