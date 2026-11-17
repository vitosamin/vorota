Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\evf.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\n261117.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT TOP 6 DateTime, EventType, EventCode FROM Events WHERE DevPtr=9 AND DateTime >= #11/17/2026 15:59:00# ORDER BY DateTime DESC")
Do While Not rs.EOF
  f.WriteLine rs("DateTime") & " type=" & rs("EventType") & " code=" & rs("EventCode")
  rs.MoveNext
Loop
conn.Close
f.Close
