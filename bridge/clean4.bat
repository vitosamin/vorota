@echo off
cd /d C:\Users\Public
del /q *.txt 2>nul
del /q *.png 2>nul
del /q GateSniff.cs GateSniff.exe compile_sniff.bat compile_sniff.vbs run_sniff.vbs GateShot.exe GateShot.cs compile_shot.* run_shot*.vbs 2>nul
del /q sniff.txt 2>nul
echo === итог === > C:\Users\Public\fin.txt
for %%F in (*.exe *.vbs *.bat *.json *.cs *.log) do echo %%F >> C:\Users\Public\fin.txt
