@echo off
set OUT=C:\Users\Public\fin_chk.txt
echo === процессы === > "%OUT%"
tasklist | findstr /i "GateBridge GateMem GateQMon GateDbPulse GateSniff GateServ GateTerm" >> "%OUT%" 2>&1
echo === задачи Gate* === >> "%OUT%"
schtasks /query /fo TABLE /nh | findstr /i "Gate" >> "%OUT%" 2>&1
echo === временные службы === >> "%OUT%"
sc query type= service state= all | findstr /i "GateSn GateQM GateMem GatePulse" >> "%OUT%" 2>&1
