Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\clock.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT DevPtr, Name, SetClockPeriod, PollingPeriod FROM Devices ORDER BY DevPtr")
Do While Not rs.EOF
  f.WriteLine "dev=" & rs("DevPtr") & " " & rs("Name") & " clock=" & rs("SetClockPeriod") & " poll=" & rs("PollingPeriod")
  rs.MoveNext
Loop
conn.Execute "UPDATE Devices SET SetClockPeriod = 0"
If Err.Number <> 0 Then f.WriteLine "update err " & Err.Description : Err.Clear
f.WriteLine "--- после ---"
Set rs = conn.Execute("SELECT DevPtr, SetClockPeriod FROM Devices ORDER BY DevPtr")
Do While Not rs.EOF
  f.WriteLine "dev=" & rs("DevPtr") & " clock=" & rs("SetClockPeriod")
  rs.MoveNext
Loop
conn.Close
f.Close
