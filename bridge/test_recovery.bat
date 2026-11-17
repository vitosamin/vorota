@echo off
set OUT=C:\Users\Public\recovery.txt
echo === kill bridge === > "%OUT%"
taskkill /IM GateBridge.exe /F >> "%OUT%" 2>&1
timeout /t 3 /nobreak > nul
echo === port after kill === >> "%OUT%"
netstat -an | findstr ":8099" | findstr LISTENING >> "%OUT%" 2>&1
echo (пусто = порт закрыт) >> "%OUT%"
echo === run watchdog === >> "%OUT%"
schtasks /run /tn GateBridgeWatchdog >> "%OUT%" 2>&1
timeout /t 20 /nobreak > nul
echo === port after watchdog === >> "%OUT%"
netstat -an | findstr ":8099" | findstr LISTENING >> "%OUT%" 2>&1
echo === process === >> "%OUT%"
tasklist /fi "imagename eq GateBridge.exe" >> "%OUT%" 2>&1
echo === watchdog log === >> "%OUT%"
type C:\Users\Public\bridge_watchdog.log >> "%OUT%" 2>&1
