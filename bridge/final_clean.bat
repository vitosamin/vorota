@echo off
cd /d C:\Users\Public
del /q run_cleanup.vbs run_dry.vbs cleanup.bat cleanup_dry.bat cleanup_list.txt cleanup_result.txt list_pub.bat check_sess.bat tasks.bat skud_task.bat finalize.bat pwd_check.bat pwd2.bat autologon.bat 2>nul
del /q *.txt 2>nul
del /q *.png 2>nul
del /q *.cs 2>nul
del /q *.ps1 2>nul
del /q csc*.log 2>nul
echo === ИТОГ === > C:\Users\Public\final.txt
dir /b C:\Users\Public\*.exe >> C:\Users\Public\final.txt 2>&1
dir /b C:\Users\Public\*.vbs >> C:\Users\Public\final.txt 2>&1
dir /b C:\Users\Public\*.bat >> C:\Users\Public\final.txt 2>&1
dir /b C:\Users\Public\*.json >> C:\Users\Public\final.txt 2>&1
dir /b C:\Users\Public\*.log >> C:\Users\Public\final.txt 2>&1
echo === TASKS === >> C:\Users\Public\final.txt
schtasks /query /fo TABLE /nh | findstr /i "Gate SKUD" >> C:\Users\Public\final.txt 2>&1
