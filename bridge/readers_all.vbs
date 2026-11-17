
Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\readers_all.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "--- all readers ORDER BY Name ---"
Set rs = conn.Execute("SELECT RdrPtr, DevPtr, Num, Name, Locked FROM Readers ORDER BY Name")
i = 0
Do While Not rs.EOF
  i = i + 1
  f.WriteLine i & vbTab & "rdr=" & rs("RdrPtr") & vbTab & "dev=" & rs("DevPtr") & vbTab & "num=" & rs("Num") & vbTab & "locked=" & rs("Locked") & vbTab & rs("Name")
  rs.MoveNext
Loop
f.WriteLine "total=" & i
f.WriteLine "--- readers with Locked=1 ---"
Set rs = conn.Execute("SELECT RdrPtr, DevPtr, Num, Name FROM Readers WHERE Locked=True ORDER BY Name")
Do While Not rs.EOF
  f.WriteLine "locked rdr=" & rs("RdrPtr") & " dev=" & rs("DevPtr") & " num=" & rs("Num") & " " & rs("Name")
  rs.MoveNext
Loop
f.WriteLine "--- grid query (window SQL) ---"
Set rs = conn.Execute("SELECT Rdr.RdrPtr, Rdr.Name AS DoorName, Rdr.Num, Dev.Address, Dev.DevPtr, Ports.PortPtr FROM (Devices AS Dev INNER JOIN Readers AS Rdr ON Dev.DevPtr=Rdr.DevPtr) INNER JOIN Ports ON Dev.PortPtr=Ports.PortPtr WHERE ((NOT Dev.DevType IN (1,10)) OR Rdr.Num=1) AND (Dev.DevType<>-1) ORDER BY Rdr.Name")
i = 0
Do While Not rs.EOF
  i = i + 1
  f.WriteLine i & vbTab & "rdr=" & rs("RdrPtr") & vbTab & "dev=" & rs("DevPtr") & vbTab & rs("DoorName")
  rs.MoveNext
Loop
f.WriteLine "grid rows=" & i
conn.Close
f.Close
