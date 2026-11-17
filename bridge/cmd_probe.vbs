
Dim fso, f, conn, rs, conn2, rs2
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\cmd_probe.txt", True)
f.WriteLine "start " & Now
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit

' offline device: DevPtr=2 "нет", PortPtr=2, Address=2, OnLine=0
conn.Execute "INSERT INTO CommandQuetch (Code, Addr, NewAddr, OperatorID, OperatorName, PortPtr, Param1, Param2, Branch) VALUES (208, 2, 0, 1, 'Admin', 2, 1, 0, 0)"
If Err.Number <> 0 Then f.WriteLine "insert err " & Err.Description Else f.WriteLine "inserted for DevPtr2 Addr=2 Port=2"
Set rs = conn.Execute("SELECT Ptr, Code, Addr, PortPtr, Param1 FROM CommandQuetch WHERE Addr=2")
If Err.Number = 0 Then
  Do While Not rs.EOF
    f.WriteLine "queued Ptr=" & rs("Ptr") & " Code=" & rs("Code") & " Addr=" & rs("Addr") & " Port=" & rs("PortPtr") & " P1=" & rs("Param1")
    rs.MoveNext
  Loop
End If
Dim i
For i = 1 To 9
  WScript.Sleep 5000
  Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch WHERE Addr=2")
  f.WriteLine "t=" & (i*5) & "s count=" & rs("C")
  If rs("C") = 0 Then Exit For
Next
Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch WHERE Addr=2")
If rs("C") > 0 Then
  conn.Execute "DELETE FROM CommandQuetch WHERE Addr=2"
  f.WriteLine "leftover deleted"
End If

' events for today
Set conn2 = CreateObject("ADODB.Connection")
conn2.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\Events\n261117.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then
  f.WriteLine "events open err " & Err.Description
Else
  Set rs2 = conn2.Execute("SELECT TOP 12 DateTime, EventType, EventCode, DevPtr, RdrPtr, UserPtr, OperatorID, Message FROM Events ORDER BY [Index] DESC")
  If Err.Number <> 0 Then f.WriteLine "events query err " & Err.Description
  Do While Not rs2.EOF
    f.WriteLine "EV " & rs2("DateTime") & " type=" & rs2("EventType") & " code=" & rs2("EventCode") & " dev=" & rs2("DevPtr") & " rdr=" & rs2("RdrPtr") & " user=" & rs2("UserPtr") & " op=" & rs2("OperatorID") & " msg=" & rs2("Message")
    rs2.MoveNext
  Loop
  conn2.Close
End If
conn.Close
f.WriteLine "done"
f.Close
