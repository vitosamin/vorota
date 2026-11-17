Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Windows\System32\taskkill.exe /IM GateBridge.exe /F", 0, True
