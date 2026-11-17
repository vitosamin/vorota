@echo off
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\Users\Public\GateDiag.exe /r:System.Drawing.dll /r:System.Windows.Forms.dll C:\Users\Public\GateDiag.cs > C:\Users\Public\csc_diag.log 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\csc_diag.log
