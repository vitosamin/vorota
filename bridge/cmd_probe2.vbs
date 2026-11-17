
Dim fso, f, conn, rs, i
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\cmd_probe2.txt", True)
f.WriteLine "start " & Now
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "Setup.RunCmd=" & conn.Execute("SELECT RunCmd FROM Setup").Fields(0).Value
conn.Execute "INSERT INTO CommandQuetch (Code, Addr, NewAddr, OperatorID, OperatorName, PortPtr, Param1, Param2, Branch) VALUES (208, 2, 0, 1, 'Admin', 2, 1, 0, 0)"
f.WriteLine "insert err=" & Err.Number
For i = 1 To 12
  WScript.Sleep 20000
  Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch WHERE Addr=2")
  f.WriteLine "t=" & (i*20) & "s count=" & rs("C")
  If rs("C") = 0 Then Exit For
Next
Set rs = conn.Execute("SELECT COUNT(*) AS C FROM CommandQuetch")
f.WriteLine "queue total=" & rs("C")
Set rs = conn.Execute("SELECT Ptr, Code, Addr, PortPtr, Param1, OperatorName FROM CommandQuetch")
Do While Not rs.EOF
  f.WriteLine "left Ptr=" & rs("Ptr") & " Code=" & rs("Code") & " Addr=" & rs("Addr") & " Port=" & rs("PortPtr") & " P1=" & rs("Param1") & " op=" & rs("OperatorName")
  rs.MoveNext
Loop
conn.Execute "DELETE FROM CommandQuetch WHERE Addr=2"
conn.Close
f.WriteLine "cleaned " & Now
f.Close
