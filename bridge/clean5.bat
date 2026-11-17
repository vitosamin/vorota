@echo off
cd /d C:\Users\Public
del /q *.txt *.png 2>nul
del /q GateProbe.exe GateSniff.exe GateSniff.cs compile_sniff.* compile_probe.* run_probe.vbs run_sniff.vbs tcp_test.ps1 2>nul
echo ok > C:\Users\Public\d.txt
