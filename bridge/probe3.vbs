
Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\probe3.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
conn.Execute "INSERT INTO CommandQuetch (Code, Addr, NewAddr, OperatorID, OperatorName, PortPtr, Param1, Param2, Branch) VALUES (208, 2, 0, 1, 'Admin', 2, 1, 0, 0)"
f.WriteLine "inserted " & Now & " err=" & Err.Number
For i = 1 To 12
  WScript.Sleep 5000
  Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch WHERE Addr=2")
  f.WriteLine "t=" & (i*5) & "s count=" & rs("C")
  If rs("C") = 0 Then
    f.WriteLine "CONSUMED at " & Now
    Exit For
  End If
Next
Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch")
f.WriteLine "queue total=" & rs("C") & " at " & Now
conn.Execute "DELETE FROM CommandQuetch WHERE Addr=2"
conn.Close
f.WriteLine "done"
f.Close
