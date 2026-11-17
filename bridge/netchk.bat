@echo off
set OUT=C:\Users\Public\net.txt
echo === GateServ PID === > "%OUT%"
tasklist /fi "imagename eq GateServ.exe" >> "%OUT%" 2>&1
echo === UDP 5000 и все соединения процесса === >> "%OUT%"
netstat -ano | findstr ":5000" >> "%OUT%" 2>&1
echo === UDP вообще === >> "%OUT%"
netstat -ano -p UDP | findstr /v "0.0.0.0:0" >> "%OUT%" 2>&1
echo === arp 192.168.9 === >> "%OUT%"
arp -a | findstr "192.168.9" >> "%OUT%" 2>&1
echo === arp всё === >> "%OUT%"
arp -a >> "%OUT%" 2>&1
