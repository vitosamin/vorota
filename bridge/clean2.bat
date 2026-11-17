@echo off
cd /d C:\Users\Public
for %%F in (*.txt) do del /q "%%F" 2>nul
if exist "60874543" del /q "60874543" 2>nul
echo === FINAL === > C:\Users\Public\final_list.txt
for %%F in (*.exe *.vbs *.bat *.json *.log) do echo %%F >> C:\Users\Public\final_list.txt
