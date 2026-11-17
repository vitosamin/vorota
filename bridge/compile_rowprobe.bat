@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateRowProbe.exe C:\Users\Public\GateRowProbe.cs > C:\Users\Public\csc_rp.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_rp.log
