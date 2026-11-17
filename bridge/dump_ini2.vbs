Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\gate_ini2.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
Set rs = conn.Execute("SELECT * FROM [Ini]")
Do While Not rs.EOF
  Dim line
  line = ""
  For i = 0 To rs.Fields.Count - 1
    line = line & rs.Fields(i).Name & "=" & rs.Fields(i).Value & " | "
  Next
  f.WriteLine line
  rs.MoveNext
Loop
conn.Close
f.WriteLine "done"
f.Close
