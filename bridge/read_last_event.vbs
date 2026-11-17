' Последнее событие «команда открывания двери» (EventType=5, EventCode=208) из журнала Gate.
' Пишет: index;dev;rdr
Option Explicit
Dim fso, outPath, f, conn, rs, name
Set fso = CreateObject("Scripting.FileSystemObject")
outPath = "C:\Users\Public\last_event.txt"
If WScript.Arguments.Count > 0 Then outPath = WScript.Arguments(0)
Set f = fso.CreateTextFile(outPath, True)
On Error Resume Next
name = "n" & Right("0" & (Year(Now) Mod 100), 2) & Right("0" & Month(Now), 2) & Right("0" & Day(Now), 2) & ".mdb"
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\" & name & ";Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then
  f.WriteLine "ERR;" & Err.Description
  f.Close
  WScript.Quit
End If
Set rs = conn.Execute("SELECT TOP 1 [Index], DevPtr, RdrPtr FROM Events WHERE EventType=5 AND EventCode=208 ORDER BY [Index] DESC")
If Err.Number <> 0 Then
  f.WriteLine "ERR;" & Err.Description
Else
  If Not rs.EOF Then
    f.WriteLine rs("Index") & ";" & rs("DevPtr") & ";" & rs("RdrPtr")
  Else
    f.WriteLine "0;0;0"
  End If
End If
conn.Close
f.Close
