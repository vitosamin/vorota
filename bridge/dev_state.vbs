
Dim fso, f, conn, rs
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\dev_state.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
Set rs = conn.Execute("SELECT * FROM Dev WHERE Ptr=9")
If Not rs.EOF Then
  Dim i
  For i = 0 To rs.Fields.Count - 1
    f.WriteLine rs.Fields(i).Name & " = " & rs.Fields(i).Value
  Next
End If
rs.Close
Set rs = conn.Execute("SELECT Rdr.Ptr, Rdr.Num, Rdr.Name, Rdr.Block, Rdr.Lock, Rdr.DevPtr FROM Rdr WHERE DevPtr=9")
Do While Not rs.EOF
  f.WriteLine "RDR " & rs("Ptr") & " num=" & rs("Num") & " block=" & rs("Block") & " lock=" & rs("Lock") & " name=" & rs("Name")
  rs.MoveNext
Loop
conn.Close
f.Close
