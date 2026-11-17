@echo off
set OUT=C:\Users\Public\gate_ini.txt
echo === C:\GATE\Gate.ini === > "%OUT%"
type C:\GATE\Gate.ini >> "%OUT%" 2>&1
