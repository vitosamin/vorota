@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateBands.exe /r:System.Drawing.dll C:\Users\Public\GateBands.cs > C:\Users\Public\csc_bands.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_bands.log
