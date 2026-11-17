@echo off
set OUT=C:\Users\Public\inst.txt
echo === процессы === > "%OUT%"
tasklist /fi "imagename eq GateBridge.exe" /v >> "%OUT%" 2>&1
echo === кто на 8099 === >> "%OUT%"
netstat -ano | findstr ":8099" >> "%OUT%" 2>&1
echo === версия файла === >> "%OUT%"
dir C:\Users\Public\GateBridge.exe >> "%OUT%" 2>&1
