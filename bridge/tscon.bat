@echo off
tscon 1 /dest:console > C:\Users\Public\tscon.txt 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\tscon.txt
timeout /t 3 /nobreak > nul
query session >> C:\Users\Public\tscon.txt 2>&1
