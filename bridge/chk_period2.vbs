Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\per3.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
Set rs = conn.Execute("SELECT ControlPeriod FROM [Ini]")
If Not rs.EOF Then f.WriteLine "ControlPeriod=" & rs("ControlPeriod")
conn.Close
f.Close
