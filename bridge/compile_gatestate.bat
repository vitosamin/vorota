@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:C:\Users\Public\GateState.exe C:\Users\Public\GateState.cs > C:\Users\Public\csc_state.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_state.log
