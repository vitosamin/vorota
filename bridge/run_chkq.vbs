Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\chk_queue.vbs", 0, True
