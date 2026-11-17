Dim fso, f, conn, rs, t0, lastDt, sql
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\watch.txt", True)
On Error Resume Next
f.WriteLine "start_server_time=" & Now()
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\n261117.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
lastDt = #1/1/2000#
Set rs = conn.Execute("SELECT TOP 1 DateTime FROM Events ORDER BY DateTime DESC")
If Not rs.EOF Then lastDt = rs("DateTime")
f.WriteLine "last_event_before=" & lastDt
t0 = Timer
Do While (Timer - t0) < 75
  Set rs = conn.Execute("SELECT TOP 10 DateTime, EventType, EventCode, DevPtr, RdrPtr FROM Events WHERE DateTime > #" & FormatDateTime(lastDt, 2) & " " & FormatDateTime(lastDt, 3) & "# ORDER BY DateTime ASC")
  Do While Not rs.EOF
    f.WriteLine Now() & " | event " & rs("DateTime") & " | type=" & rs("EventType") & " code=" & rs("EventCode") & " dev=" & rs("DevPtr") & " rdr=" & rs("RdrPtr")
    lastDt = rs("DateTime")
    rs.MoveNext
  Loop
  WScript.Sleep 150
Loop
conn.Close
f.WriteLine "done " & Now()
f.Close
