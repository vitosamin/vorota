Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd.exe /c C:\Users\Public\make_watchdog.bat", 0, True
