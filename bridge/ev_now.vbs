
Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\ev_now.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\n261117.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "--- все события после 12:04 ---"
Set rs = conn.Execute("SELECT DateTime, EventType, EventCode, DevPtr, RdrPtr, Message FROM Events WHERE DateTime >= #11/17/2026 12:04:00# ORDER BY [Index] ASC")
Do While Not rs.EOF
  f.WriteLine rs("DateTime") & " type=" & rs("EventType") & " code=" & rs("EventCode") & " dev=" & rs("DevPtr") & " rdr=" & rs("RdrPtr") & " | " & rs("Message")
  rs.MoveNext
Loop
conn.Close
f.Close
