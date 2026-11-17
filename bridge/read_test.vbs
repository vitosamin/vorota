Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\SysWOW64\cscript.exe //nologo C:\Users\Public\read_last_event.vbs C:\Users\Public\last_event.txt", 0, True
