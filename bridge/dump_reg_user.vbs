Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd.exe /c reg query ""HKCU\Software\VB and VBA Program Settings"" /s > C:\Users\Public\reg_user.txt 2>&1", 0, True
sh.Run "cmd.exe /c reg query ""HKCU\Software"" /s 2>&1 | findstr /i ""gate period terminal door open"" >> C:\Users\Public\reg_user.txt 2>&1", 0, True
