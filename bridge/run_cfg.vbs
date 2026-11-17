Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\dump_cfg.vbs", 0, True
