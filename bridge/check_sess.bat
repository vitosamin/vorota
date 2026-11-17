@echo off
set OUT=C:\Users\Public\sess.txt
qwinsta > "%OUT%" 2>&1
echo === query user === >> "%OUT%"
query user >> "%OUT%" 2>&1
echo === tasklist === >> "%OUT%"
tasklist /fi "imagename eq GateTerm.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
tasklist /fi "imagename eq GateBridge.exe" >> "%OUT%" 2>&1
