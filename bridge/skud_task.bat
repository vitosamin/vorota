@echo off
set OUT=C:\Users\Public\skud_task.txt
schtasks /query /tn SKUD /fo LIST /v > "%OUT%" 2>&1
echo === processes === >> "%OUT%"
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateTerm.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateMonitor.exe" >> "%OUT%" 2>&1
