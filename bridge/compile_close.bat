@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateClose.exe C:\Users\Public\GateClose.cs > C:\Users\Public\csc_close.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_close.log
