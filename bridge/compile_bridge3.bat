@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\Users\Public\GateBridge.exe C:\Users\Public\GateBridge.cs C:\Users\Public\WebAuth.cs > C:\Users\Public\csc_bridge3.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_bridge3.log
