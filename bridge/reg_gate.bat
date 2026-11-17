@echo off
set OUT=C:\Users\Public\gate_reg.txt
echo === загрузка куста skudnew === > "%OUT%"
reg load HKU\skudnew_hive C:\Users\skudnew\NTUSER.DAT >> "%OUT%" 2>&1
echo === VB/VBA Program Settings === >> "%OUT%"
reg query "HKU\skudnew_hive\Software\VB and VBA Program Settings" /s >> "%OUT%" 2>&1
echo === Software\Gate* === >> "%OUT%"
reg query "HKU\skudnew_hive\Software" /s 2>&1 | findstr /i "gate period open door terminal" >> "%OUT%" 2>&1
echo === выгрузка === >> "%OUT%"
reg unload HKU\skudnew_hive >> "%OUT%" 2>&1
