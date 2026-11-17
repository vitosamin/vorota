@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GatePress.exe C:\Users\Public\GatePress.cs > C:\Users\Public\csc_press.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_press.log
