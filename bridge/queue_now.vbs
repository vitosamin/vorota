
Dim fso, f, conn, rs, t
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\queue_now.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "--- CommandQuetch ---"
Set rs = conn.Execute("SELECT Ptr, Code, Addr, PortPtr, Param1, Param2, OperatorID, OperatorName FROM CommandQuetch")
Do While Not rs.EOF
  f.WriteLine "Ptr=" & rs("Ptr") & " Code=" & rs("Code") & " Addr=" & rs("Addr") & " Port=" & rs("PortPtr") & " P1=" & rs("Param1") & " P2=" & rs("Param2") & " op=" & rs("OperatorID") & "/" & rs("OperatorName")
  rs.MoveNext
Loop
f.WriteLine "--- Results ---"
Set rs = conn.Execute("SELECT * FROM Results")
Do While Not rs.EOF
  f.WriteLine "Ptr=" & rs("Ptr") & " Success=" & rs("Success") & " Str=" & rs("StringResult") & " Num=" & rs("NumericResult")
  rs.MoveNext
Loop
f.WriteLine "--- Servers ---"
Set rs = conn.Execute("SELECT * FROM Servers")
Do While Not rs.EOF
  f.WriteLine "SrvPtr=" & rs("SrvPtr") & " Name=" & rs("SrvName") & " Path=" & rs("SrvPath") & " Type=" & rs("SrvType")
  rs.MoveNext
Loop
conn.Close
f.WriteLine "--- nEvBuf tables ---"
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\nEvBuf.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number = 0 Then
  Set rs = conn.Execute("SELECT COUNT(*) AS C FROM Events")
  f.WriteLine "nEvBuf events=" & rs("C")
  Set rs = conn.Execute("SELECT TOP 10 DateTime, EventType, EventCode, DevPtr, RdrPtr, OperatorID, Message FROM Events ORDER BY [Index] DESC")
  Do While Not rs.EOF
    f.WriteLine "EV " & rs("DateTime") & " type=" & rs("EventType") & " code=" & rs("EventCode") & " dev=" & rs("DevPtr") & " rdr=" & rs("RdrPtr") & " op=" & rs("OperatorID") & " | " & rs("Message")
    rs.MoveNext
  Loop
  conn.Close
Else
  f.WriteLine "nEvBuf open err " & Err.Description
End If
f.WriteLine "done"
f.Close
