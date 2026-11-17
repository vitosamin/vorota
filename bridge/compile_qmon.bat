@echo off
C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /nologo /platform:x86 /out:C:\Users\Public\GateQMon.exe /r:System.Data.dll C:\Users\Public\GateQMon.cs > C:\Users\Public\csc_qmon.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_qmon.log
