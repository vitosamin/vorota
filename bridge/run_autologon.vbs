Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s cmd.exe /c C:\Users\Public\autologon.bat", 0, True
