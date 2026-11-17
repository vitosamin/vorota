@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateAcc.exe /r:Microsoft.CSharp.dll C:\Users\Public\GateAcc.cs > C:\Users\Public\csc_gacc.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_gacc.log
