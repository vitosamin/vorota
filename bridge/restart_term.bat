@echo off
taskkill /IM GateTerm.exe /F > nul 2>&1
timeout /t 3 /nobreak > nul
C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u "ALM\skudnew" -p "Admin910327" -w "C:\GATE\Terminal" -d "C:\GATE\Terminal\GateTerm.exe" > nul 2>&1
timeout /t 12 /nobreak > nul
tasklist /fi "imagename eq GateTerm.exe" > C:\Users\Public\term.txt 2>&1
