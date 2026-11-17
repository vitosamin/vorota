
Dim fso, f, conn, rs, i, seen
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\watch_queue.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "watch start " & Now
For i = 1 To 120
  Set rs = conn.Execute("SELECT Ptr, Code, Addr, PortPtr, Param1, Param2, OperatorID, OperatorName FROM CommandQuetch")
  If Err.Number <> 0 Then
    f.WriteLine "q err " & Err.Description
    Err.Clear
  Else
    Do While Not rs.EOF
      f.WriteLine Now & " ROW Ptr=" & rs("Ptr") & " Code=" & rs("Code") & " Addr=" & rs("Addr") & " Port=" & rs("PortPtr") & " P1=" & rs("Param1") & " P2=" & rs("Param2") & " op=" & rs("OperatorID") & "/" & rs("OperatorName")
      rs.MoveNext
    Loop
  End If
  WScript.Sleep 250
Next
Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch")
f.WriteLine "final queue total=" & rs("C") & " at " & Now
conn.Execute "DELETE FROM CommandQuetch"
conn.Close
f.WriteLine "watch done"
f.Close
