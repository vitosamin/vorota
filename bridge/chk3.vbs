Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\chk3.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT ControlPeriod FROM [Ini]")
If Not rs.EOF Then f.WriteLine "ControlPeriod=" & rs("ControlPeriod")
Set rs = conn.Execute("SELECT DevPtr, PollingPeriod, SetClockPeriod FROM Devices ORDER BY DevPtr")
Do While Not rs.EOF
  f.WriteLine "dev=" & rs("DevPtr") & " poll=" & rs("PollingPeriod") & " clock=" & rs("SetClockPeriod")
  rs.MoveNext
Loop
conn.Close
f.Close
