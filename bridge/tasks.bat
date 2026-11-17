@echo off
set OUT=C:\Users\Public\tasks.txt
schtasks /query /fo TABLE /nh > "%OUT%" 2>&1
echo === delete leftovers === >> "%OUT%"
schtasks /delete /tn GatePsTest /f >> "%OUT%" 2>&1
schtasks /delete /tn GateS1 /f >> "%OUT%" 2>&1
schtasks /delete /tn GateSession1 /f >> "%OUT%" 2>&1
echo === gate tasks after === >> "%OUT%"
schtasks /query /fo TABLE /nh | findstr /i "gate" >> "%OUT%" 2>&1
