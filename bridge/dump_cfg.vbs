Dim fso, f, conn, rs, t
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\gate_cfg.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "=== таблицы ==="
Set rs = conn.OpenSchema(20)
Do While Not rs.EOF
  f.WriteLine rs("TABLE_NAME").Value
  rs.MoveNext
Loop
rs.Close
f.WriteLine "=== возможные настройки ==="
Set rs = conn.OpenSchema(20)
Do While Not rs.EOF
  t = rs("TABLE_NAME").Value
  If InStr(1, t, "Set", 1) > 0 Or InStr(1, t, "Param", 1) > 0 Or InStr(1, t, "Config", 1) > 0 Or InStr(1, t, "Const", 1) > 0 Then
    f.WriteLine "--- " & t
    Dim rs2
    Set rs2 = conn.Execute("SELECT * FROM [" & t & "]")
    Dim i
    Do While Not rs2.EOF
      For i = 0 To rs2.Fields.Count - 1
        f.WriteLine "  " & rs2.Fields(i).Name & " = " & rs2.Fields(i).Value
      Next
      rs2.MoveNext
    Loop
    rs2.Close
  End If
  rs.MoveNext
Loop
conn.Close
f.WriteLine "done"
f.Close
