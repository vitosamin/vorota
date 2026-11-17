@echo off
query session > C:\Users\Public\sessions.txt 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\sessions.txt
query user >> C:\Users\Public\sessions.txt 2>&1
