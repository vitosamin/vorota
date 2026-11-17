@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateGridClip.exe C:\Users\Public\GateGridClip.cs > C:\Users\Public\csc_gridclip.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_gridclip.log
