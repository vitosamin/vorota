@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateClip2.exe C:\Users\Public\GateClip2.cs > C:\Users\Public\csc_clip2.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_clip2.log
