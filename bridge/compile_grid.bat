@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateGrid.exe /r:Microsoft.CSharp.dll C:\Users\Public\GateGrid.cs > C:\Users\Public\csc_grid.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_grid.log
