@echo off
set OUT=C:\Users\Public\hklm.txt
echo === HKLM SOFTWARE\GATE === > "%OUT%"
reg query "HKLM\SOFTWARE\GATE" /s >> "%OUT%" 2>&1
echo === поиск gate в HKLM\SOFTWARE === >> "%OUT%"
reg query "HKLM\SOFTWARE" /f "gate" /k >> "%OUT%" 2>&1
echo === Wow6432Node === >> "%OUT%"
reg query "HKLM\SOFTWARE\Wow6432Node\GATE" /s >> "%OUT%" 2>&1
echo === службы Gate === >> "%OUT%"
sc query type= service state= all | findstr /i "gate" >> "%OUT%" 2>&1
