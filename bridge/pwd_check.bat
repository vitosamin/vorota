@echo off
net use \\127.0.0.1\IPC$ /user:SKUD\skudnew Admin910327 > C:\Users\Public\pwd_check.txt 2>&1
echo local_rc=%ERRORLEVEL% >> C:\Users\Public\pwd_check.txt
net use \\127.0.0.1\IPC$ /delete >> C:\Users\Public\pwd_check.txt 2>&1
net use \\127.0.0.1\IPC$ /user:ALM\skudnew Admin910327 >> C:\Users\Public\pwd_check.txt 2>&1
echo domain_rc=%ERRORLEVEL% >> C:\Users\Public\pwd_check.txt
net use \\127.0.0.1\IPC$ /delete >> C:\Users\Public\pwd_check.txt 2>&1
