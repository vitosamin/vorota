Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\ports2.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
f.WriteLine "=== Ports (имя, адрес, интервал, таймаут) ==="
Set rs = conn.Execute("SELECT PortPtr, PortName, PortAddr, PortType, PollingInterval, ReplyTimeout, RestoreTimeout FROM Ports")
Do While Not rs.EOF
  f.WriteLine "port=" & rs("PortPtr") & " " & rs("PortName") & " " & rs("PortAddr") & " type=" & rs("PortType") & " poll=" & rs("PollingInterval") & " reply=" & rs("ReplyTimeout") & " restore=" & rs("RestoreTimeout")
  rs.MoveNext
Loop
f.WriteLine "=== Devices для порта 9 ==="
Set rs = conn.Execute("SELECT * FROM Devices WHERE PortPtr=9")
Do While Not rs.EOF
  Dim line: line = ""
  For i = 0 To rs.Fields.Count - 1
    line = line & rs.Fields(i).Name & "=" & rs.Fields(i).Value & " | "
  Next
  f.WriteLine line
  rs.MoveNext
Loop
conn.Close
f.Close
