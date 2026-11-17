$targets = @('192.168.9.56','192.168.9.50','192.168.9.53','192.168.9.54','192.168.9.55','192.168.9.52','192.168.9.100')
$out = 'C:\Users\Public\tcp_test.txt'
"=== проверка второго подключения ===" | Out-File -FilePath $out -Encoding utf8
foreach ($t in $targets) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $r = $c.BeginConnect($t, 5000, $null, $null)
    $ok = $r.AsyncWaitHandle.WaitOne(1500)
    if ($ok -and $c.Connected) {
      "$t : ПОДКЛЮЧЕНИЕ ЕСТЬ" | Out-File -FilePath $out -Append -Encoding utf8
      $c.Close()
    } else {
      "$t : нет (таймаут)" | Out-File -FilePath $out -Append -Encoding utf8
    }
  } catch {
    "$t : ошибка $($_.Exception.Message)" | Out-File -FilePath $out -Append -Encoding utf8
  }
}
