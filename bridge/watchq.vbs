Dim fso, f, conn, rs, i, t0, n
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\watchq.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "start " & Now()
t0 = Timer
Do While (Timer - t0) < 18
  Set rs = conn.Execute("SELECT COUNT(*) AS c FROM CommandQuetch")
  n = -1
  If Not rs.EOF Then n = rs("c")
  If n > 0 Then
    f.WriteLine Now() & " В ОЧЕРЕДИ " & n
    Set rs = conn.Execute("SELECT * FROM CommandQuetch")
    Do While Not rs.EOF
      Dim line: line = ""
      For i = 0 To rs.Fields.Count - 1
        line = line & rs.Fields(i).Name & "=" & rs.Fields(i).Value & " | "
      Next
      f.WriteLine "    " & line
      rs.MoveNext
    Loop
  End If
  WScript.Sleep 100
Loop
conn.Close
f.WriteLine "done " & Now()
f.Close
