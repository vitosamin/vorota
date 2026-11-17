Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s C:\Users\Public\GateQMon.exe 30 C:\Users\Public\qmon.txt", 0, True
WScript.Sleep 32000
