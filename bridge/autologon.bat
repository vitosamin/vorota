@echo off
set OUT=C:\Users\Public\autologon.txt
echo === Run keys === > "%OUT%"
reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" >> "%OUT%" 2>&1
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" >> "%OUT%" 2>&1
echo === Startup folders === >> "%OUT%"
dir /b "C:\Users\skudnew\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup" >> "%OUT%" 2>&1
dir /b "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup" >> "%OUT%" 2>&1
echo === Winlogon before === >> "%OUT%"
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon >> "%OUT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName >> "%OUT%" 2>&1
echo === set autologon === >> "%OUT%"
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f >> "%OUT%" 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d ALM /f >> "%OUT%" 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d skudnew /f >> "%OUT%" 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /t REG_SZ /d Admin910327 /f >> "%OUT%" 2>&1
reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoLogonCount /f >> "%OUT%" 2>&1
echo === Winlogon after === >> "%OUT%"
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon >> "%OUT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName >> "%OUT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName >> "%OUT%" 2>&1
