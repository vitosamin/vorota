Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\period.txt", True)
On Error Resume Next
' резервная копия
If Not fso.FileExists("C:\GATE\Server\config.mdb.bak-20261117") Then
  fso.CopyFile "C:\GATE\Server\config.mdb", "C:\GATE\Server\config.mdb.bak-20261117", True
End If
If Err.Number <> 0 Then f.WriteLine "backup err " & Err.Description : Err.Clear
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
conn.Execute "UPDATE [Ini] SET ControlPeriod = 1"
If Err.Number <> 0 Then f.WriteLine "update err " & Err.Description : Err.Clear
Set rs = conn.Execute("SELECT ControlPeriod FROM [Ini]")
If Not rs.EOF Then f.WriteLine "ControlPeriod теперь = " & rs("ControlPeriod")
conn.Close
f.WriteLine "done"
f.Close
