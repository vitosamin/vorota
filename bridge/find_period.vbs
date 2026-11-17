Dim fso, f, conn, rs, rs2, i, t, found
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\Users\Public\periods.txt", True)
On Error Resume Next
Set conn = CreateObject("ADODB.Connection")
conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
If Err.Number <> 0 Then f.WriteLine "open err " & Err.Description : f.Close : WScript.Quit
Set rs = conn.OpenSchema(20)
Do While Not rs.EOF
  t = rs("TABLE_NAME").Value
  If Left(t, 1) <> "M" And Left(t, 1) <> "p" Then
    Set rs2 = conn.Execute("SELECT * FROM [" & t & "]")
    If Err.Number = 0 Then
      Dim fld
      For Each fld In rs2.Fields
        Dim nm: nm = fld.Name
        Dim low: low = LCase(nm)
        If InStr(low, "period") > 0 Or InStr(low, "interval") > 0 Or InStr(low, "timeout") > 0 Or InStr(low, "timer") > 0 Or InStr(low, "delay") > 0 Then
          If Not rs2.EOF Then f.WriteLine t & "." & nm & " = " & rs2.Fields(nm).Value
        End If
      Next
    End If
    Err.Clear
  End If
  rs.MoveNext
Loop
f.WriteLine "done"
conn.Close
f.Close
