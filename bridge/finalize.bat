@echo off
set OUT=C:\Users\Public\finalize.txt
schtasks /change /tn SKUD /enable >> "%OUT%" 2>&1
schtasks /query /tn SKUD /fo LIST | findstr /i "Состояние" >> "%OUT%" 2>&1
echo === bridge startup task === >> "%OUT%"
schtasks /query /tn GateBridgeStartup /fo LIST /v | findstr /i "Задача для выполнения Состояние Режим" >> "%OUT%" 2>&1
echo === kill stray GateMonitor === >> "%OUT%"
taskkill /IM GateMonitor.exe /F >> "%OUT%" 2>&1
echo === processes === >> "%OUT%"
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateTerm.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateBridge.exe" >> "%OUT%" 2>&1
