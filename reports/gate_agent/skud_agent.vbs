' SKUD Gate: queue agent. Started by bridge_watchdog.bat every 2 minutes.
'   *.sql        - one statement per line, '#' starts a comment (file in cp1251).
'   *.cmd/*.bat  - executed LINE BY LINE through cmd.exe; running a .cmd file
'                  directly on this host fails with rc=1.
' Result is written next to the job as <name>.result (ok=N / err=N:text).
' SQL runs in the first pass and commands in the second, so a broken command can
' never block writing to the database. Every file is processed under
' "On Error Resume Next": one bad job must not stop the whole queue.
Option Explicit
Dim fso, qdir, f, ts, conn, line, n, res, outName, sh, rc, ext
Set fso = CreateObject("Scripting.FileSystemObject")
qdir = "C:\GATE\_skud_queue\"
If Not fso.FolderExists(qdir) Then WScript.Quit

Sub SafeMove(f, qdir)
  Dim dst
  dst = qdir & "done\" & f.Name
  On Error Resume Next
  If fso.FileExists(dst) Then fso.DeleteFile dst, True
  f.Move dst
  Err.Clear
  On Error Goto 0
End Sub

' ---- 1) SQL ----
For Each f In fso.GetFolder(qdir).Files
  ext = LCase(fso.GetExtensionName(f.Name))
  If ext = "sql" Then
    outName = qdir & fso.GetBaseName(f.Name) & ".result"
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
    Set ts = fso.CreateTextFile(outName, True)
    ts.Write res
    ts.Close
    Err.Clear
    On Error Goto 0
    SafeMove f, qdir
  End If
Next

' ---- 2) commands ----
For Each f In fso.GetFolder(qdir).Files
  ext = LCase(fso.GetExtensionName(f.Name))
  If ext = "cmd" Or ext = "bat" Then
    outName = qdir & fso.GetBaseName(f.Name) & ".result"
    Set sh = CreateObject("WScript.Shell")
    On Error Resume Next
    Set ts = fso.OpenTextFile(f.Path, 1)
    Do Until ts.AtEndOfStream
      line = Trim(ts.ReadLine)
      If Len(line) > 0 And Left(line, 1) <> "@" And Left(line, 1) <> ":" Then
        rc = sh.Run("cmd.exe /c " & line & " >> """ & outName & """ 2>&1", 0, True)
      End If
    Loop
    ts.Close
    Err.Clear
    On Error Goto 0
    SafeMove f, qdir
  End If
Next
