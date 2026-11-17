@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateSniff2.exe C:\Users\Public\GateSniff2.cs > C:\Users\Public\csc_sniff2.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_sniff2.log
