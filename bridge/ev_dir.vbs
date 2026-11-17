
Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\ev_dir.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\n261117.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT TOP 6 DateTime, EventType, EventCode, DevPtr, RdrPtr FROM Events WHERE EventType=2 AND EventCode=4 ORDER BY [Index] DESC")
Do While Not rs.EOF
  f.WriteLine rs("DateTime") & " code=4 dev=" & rs("DevPtr") & " rdr=" & rs("RdrPtr")
  rs.MoveNext
Loop
conn.Close
f.Close
