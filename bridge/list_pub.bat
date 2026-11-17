@echo off
set OUT=C:\Users\Public\pub_list.txt
echo === exe === > "%OUT%"
dir /b C:\Users\Public\*.exe >> "%OUT%" 2>&1
echo === vbs/bat === >> "%OUT%"
dir /b C:\Users\Public\*.vbs >> "%OUT%" 2>&1
dir /b C:\Users\Public\*.bat >> "%OUT%" 2>&1
echo === json/log/txt === >> "%OUT%"
dir /b C:\Users\Public\*.json >> "%OUT%" 2>&1
dir /b C:\Users\Public\*.log >> "%OUT%" 2>&1
echo === tasks === >> "%OUT%"
schtasks /query /fo TABLE /nh | findstr /i "Gate SKUD" >> "%OUT%" 2>&1
echo === processes === >> "%OUT%"
tasklist | findstr /i "Gate gate" >> "%OUT%" 2>&1
