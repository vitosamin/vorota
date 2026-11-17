Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd.exe /c C:\Users\Public\reg_hklm.bat", 0, True
