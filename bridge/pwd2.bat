@echo off
net use \\127.0.0.1\IPC$ /delete > nul 2>&1
net use \\127.0.0.1\IPC$ /user:ALM\skudnew Admin910327 > C:\Users\Public\pwd2.txt 2>&1
echo rc=%ERRORLEVEL% >> C:\Users\Public\pwd2.txt
net use \\127.0.0.1\IPC$ /delete >> C:\Users\Public\pwd2.txt 2>&1
whoami /user >> C:\Users\Public\pwd2.txt 2>&1
wmic useraccount where name='skudnew' get Name,Domain,SID,Disabled /format:list >> C:\Users\Public\pwd2.txt 2>&1
