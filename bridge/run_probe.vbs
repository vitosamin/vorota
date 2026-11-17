Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\System32\cscript.exe //nologo C:\Users\Public\compile_probe.vbs", 0, True
sh.Run "C:\Users\Public\GateProbe.exe", 0, True
