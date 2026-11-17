Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s C:\Users\Public\GateDbPulse.exe 20 C:\Users\Public\pulse.txt", 0, True
WScript.Sleep 22000
