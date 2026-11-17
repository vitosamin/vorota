' СКУД Gate: агент очереди. Запускается сторожем (bridge_watchdog.bat) каждые 2 минуты.
' Читает *.sql из C:\GATE\_skud_queue, выполняет по одной команде в строке,
' пишет рядом <имя>.result со строками ok / err=...
Option Explicit
Dim fso, qdir, folder, f, ts, conn, line, n, res, outName, errLine
Set fso = CreateObject("Scripting.FileSystemObject")
qdir = "C:\GATE\_skud_queue\"
If Not fso.FolderExists(qdir) Then WScript.Quit
For Each f In fso.GetFolder(qdir).Files
  If LCase(fso.GetExtensionName(f.Name)) = "sql" Then
    res = ""
    errLine = ""
    On Error Resume Next
    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
    If Err.Number <> 0 Then
      res = res & "err=open " & Err.Description & vbCrLf
      Err.Clear
    Else
      Set ts = fso.OpenTextFile(f.Path, 1)
      n = 0
      Do Until ts.AtEndOfStream
        line = Trim(ts.ReadLine)
        If Len(line) > 0 And Left(line, 1) <> "#" Then
          n = n + 1
          conn.Execute line
          If Err.Number <> 0 Then
            res = res & "err=" & n & ":" & Err.Description & vbCrLf
            Err.Clear
          Else
            res = res & "ok=" & n & vbCrLf
          End If
        End If
      Loop
      ts.Close
      conn.Close
    End If
    On Error Goto 0
    outName = qdir & fso.GetBaseName(f.Name) & ".result"
    Set ts = fso.CreateTextFile(outName, True)
    ts.Write res
    ts.Close
    f.Move qdir & "done\" & f.Name
  End If
Next
