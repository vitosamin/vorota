Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\eva.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT COUNT(*) AS c FROM EventActions")
If Not rs.EOF Then f.WriteLine "EventActions rows=" & rs("c")
Set rs = conn.Execute("SELECT TOP 5 * FROM EventActions")
Do While Not rs.EOF
  Dim line: line = ""
  For i = 0 To rs.Fields.Count - 1
    line = line & rs.Fields(i).Name & "=" & rs.Fields(i).Value & " | "
  Next
  f.WriteLine line
  rs.MoveNext
Loop
f.WriteLine "=== OperEventTypes ==="
Set rs = conn.Execute("SELECT TOP 30 * FROM OperEventTypes")
Do While Not rs.EOF
  f.WriteLine "  Code=" & rs("Code") & " Name=" & rs("Name")
  rs.MoveNext
Loop
conn.Close
f.Close
