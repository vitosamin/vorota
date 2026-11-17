Dim fso, f, conn, rs, i, t0, n, prev
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\watchq2.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
f.WriteLine "start_timer=" & FormatNumber(Timer, 3)
prev = -1
t0 = Timer
Do While (Timer - t0) < 20
  n = -1
  Set rs = conn.Execute("SELECT COUNT(*) AS c FROM CommandQuetch")
  If Not rs.EOF Then n = rs("c")
  If n <> prev Then
    f.WriteLine "t=" & FormatNumber(Timer, 3) & " queue=" & n
    prev = n
  End If
  WScript.Sleep 30
Loop
f.WriteLine "done_timer=" & FormatNumber(Timer, 3)
conn.Close
f.Close
