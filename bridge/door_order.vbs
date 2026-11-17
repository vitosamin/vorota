
Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\door_order.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
Set rs = conn.Execute("SELECT Rdr.RdrPtr, Rdr.Name AS DoorName, Rdr.Num, Dev.Address, Dev.DevPtr, Ports.PortPtr, Dev.DevType, Ports.PortAddr, Dev.OnLine FROM (Devices AS Dev INNER JOIN Readers AS Rdr ON Dev.DevPtr=Rdr.DevPtr) INNER JOIN Ports ON Dev.PortPtr=Ports.PortPtr WHERE ((NOT Dev.DevType IN (1,10)) OR Rdr.Num=1) AND (Dev.DevType<>-1) ORDER BY Rdr.Name")
If Err.Number <> 0 Then f.WriteLine "q err " & Err.Description
i = 0
Do While Not rs.EOF
  i = i + 1
  f.WriteLine i & vbTab & "rdr=" & rs("RdrPtr") & vbTab & "num=" & rs("Num") & vbTab & "dev=" & rs("DevPtr") & vbTab & "addr=" & rs("Address") & vbTab & "port=" & rs("PortPtr") & vbTab & "ip=" & rs("PortAddr") & vbTab & "online=" & rs("OnLine") & vbTab & rs("DoorName")
  rs.MoveNext
Loop
f.WriteLine "rows=" & i
conn.Close
f.Close
