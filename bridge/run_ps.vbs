Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd.exe /c C:\Users\Public\ps_chk.bat > C:\Users\Public\ps.txt 2>&1", 0, True
