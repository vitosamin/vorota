@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateDoor.exe C:\Users\Public\GateDoor.cs > C:\Users\Public\csc_gatedoor.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_gatedoor.log
