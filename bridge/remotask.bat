schtasks /change /tn GateBridgeWatchdog /tr "C:\Users\Public\bridge_watchdog.bat" > C:\Users\Public\remotask.txt 2>&1
schtasks /query /tn GateBridgeWatchdog /fo LIST /v | findstr /i "Повторять Состояние Включено" >> C:\Users\Public\remotask.txt 2>&1
