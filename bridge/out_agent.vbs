' СКУД Gate: агент очереди. Запускается сторожем (bridge_watchdog.bat) каждые 2 минуты.
' Выполняет *.sql (по одной команде в строке) и *.cmd/*.bat из C:\GATE\_skud_queue.
' Рядом пишет <имя>.result: строки ok=N / err=N:текст
Option Explicit
Dim fso, qdir, f, ts, conn, line, n, res, outName, sh, rc, ext
Set fso = CreateObject("Scripting.FileSystemObject")
qdir = "C:\GATE\_skud_queue\"
If Not fso.FolderExists(qdir) Then WScript.Quit

For Each f In fso.GetFolder(qdir).Files
  ext = LCase(fso.GetExtensionName(f.Name))
  outName = qdir & fso.GetBaseName(f.Name) & ".result"

  If ext = "cmd" Or ext = "bat" Then
    Set sh = CreateObject("WScript.Shell")
    rc = sh.Run("cmd /c """ & f.Path & """ > """ & outName & """ 2>&1", 0, True)
    f.Move qdir & "done\" & f.Name
  End If

  If ext = "sql" Then
    res = ""
    On Error Resume Next
    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\GATE\Server\config.mdb;Jet OLEDB:System database=C:\GATE\Server\Gate.mdw;User ID=master;Password=masterio0;"
    If Err.Number <> 0 Then
      res = "err=open " & Err.Description & vbCrLf
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
    Set ts = fso.CreateTextFile(outName, True)
    ts.Write res
    ts.Close
    f.Move qdir & "done\" & f.Name
  End If
Next
