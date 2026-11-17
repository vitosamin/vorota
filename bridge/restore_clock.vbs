Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\fix.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
' вернуть синхронизацию часов как было: dev1 и dev9 = 5, остальные 60
conn.Execute "UPDATE Devices SET SetClockPeriod = 60"
conn.Execute "UPDATE Devices SET SetClockPeriod = 5 WHERE DevPtr IN (1,9)"
f.WriteLine "=== часы восстановлены ==="
Set rs = conn.Execute("SELECT DevPtr, Name, SetClockPeriod, PollingPeriod FROM Devices ORDER BY DevPtr")
Do While Not rs.EOF
  f.WriteLine "dev=" & rs("DevPtr") & " " & rs("Name") & " clock=" & rs("SetClockPeriod") & " poll=" & rs("PollingPeriod")
  rs.MoveNext
Loop
f.WriteLine "=== Outputs (первые 3) ==="
Set rs = conn.Execute("SELECT TOP 3 * FROM Outputs")
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
