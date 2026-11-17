using System;
using System.IO;
using System.Net.Sockets;
using System.Text;

class GateProbe
{
    static void Main()
    {
        var log = new StreamWriter(@"C:\Users\Public\probe.txt", false, new UTF8Encoding(false));
        string[] targets = { "192.168.9.56", "192.168.9.50", "192.168.9.53" };
        foreach (string t in targets)
        {
            try
            {
                using (var c = new TcpClient())
                {
                    var ar = c.BeginConnect(t, 5000, null, null);
                    bool ok = ar.AsyncWaitHandle.WaitOne(1500);
                    if (ok && c.Connected)
                    {
                        log.WriteLine(t + " : ПОДКЛЮЧЕНИЕ ЕСТЬ");
                        // пробуем прочитать приветствие (если контроллер сам что-то шлёт)
                        c.ReceiveTimeout = 800;
                        var buf = new byte[64];
                        try
                        {
                            int n = c.GetStream().Read(buf, 0, buf.Length);
                            if (n > 0) log.WriteLine("   пришло " + n + " байт: " + Hex(buf, n));
                            else log.WriteLine("   (данных нет)");
                        }
                        catch { log.WriteLine("   (данных нет)"); }
                        c.Close();
                    }
                    else log.WriteLine(t + " : нет (таймаут)");
                }
            }
            catch (Exception e) { log.WriteLine(t + " : ошибка " + e.Message); }
        }
        log.WriteLine("done");
        log.Close();
    }

    static string Hex(byte[] d, int n)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.Append(d[i].ToString("X2")).Append(' ');
        return sb.ToString();
    }
}
