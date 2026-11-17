Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd.exe /c reg query ""HKCU\Software\GATE-Server-Terminal"" /s > C:\Users\Public\reg2.txt 2>&1", 0, True
