using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/// <summary>Сниффер UDP-трафика к контроллерам (для разбора протокола).
/// Запуск: GateSniff.exe <секунд> <ip-фильтр> <файл-вывода></summary>
class GateSniff
{
    static void Main(string[] args)
    {
        int seconds = args.Length > 0 ? int.Parse(args[0]) : 20;
        string filter = args.Length > 1 ? args[1] : "192.168.9.";
        string outPath = args.Length > 2 ? args[2] : @"C:\Users\Public\sniff.txt";

        var log = new StreamWriter(outPath, false, new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " filter=" + filter);

        Socket sock = new Socket(AddressFamily.InterNetwork, SocketType.Raw, ProtocolType.IP);
        sock.Bind(new IPEndPoint(IPAddress.Parse(LocalIp()), 0));
        sock.IOControl(IOControlCode.ReceiveAll, new byte[] { 1, 0, 0, 0 }, null);
        sock.ReceiveTimeout = 200;

        var deadline = DateTime.UtcNow.AddSeconds(seconds);
        var buf = new byte[65535];
        int count = 0;
        while (DateTime.UtcNow < deadline)
        {
            int n;
            try { n = sock.Receive(buf); }
            catch (SocketException) { continue; }
            if (n < 28) continue;
            int ihl = (buf[0] & 0x0F) * 4;
            int proto = buf[9];
            string src = buf[12] + "." + buf[13] + "." + buf[14] + "." + buf[15];
            string dst = buf[16] + "." + buf[17] + "." + buf[18] + "." + buf[19];
            if (!src.StartsWith(filter) && !dst.StartsWith(filter)) continue;
            int sport = (buf[ihl] << 8) | buf[ihl + 1];
            int dport = (buf[ihl + 2] | (buf[ihl + 3] << 8));
            dport = (buf[ihl + 2] << 8) | buf[ihl + 3];
            int len, hdr;
            if (proto == 17) { len = ((buf[ihl + 4] << 8) | buf[ihl + 5]) - 8; hdr = ihl + 8; }
            else if (proto == 6)
            {
                int doff = (buf[ihl + 12] >> 4) * 4;
                int total = (buf[2] << 8) | buf[3];
                len = total - ihl - doff;
                hdr = ihl + doff;
                if (sport != 5000 && dport != 5000) continue;
            }
            else continue;
            if (len < 0) continue;
            var payload = new byte[len];
            Array.Copy(buf, hdr, payload, 0, Math.Min(len, n - hdr));
            log.WriteLine(DateTime.Now.ToString("HH:mm:ss.fff") + " " + src + ":" + sport + " -> " + dst + ":" + dport + " len=" + len);
            log.WriteLine("   " + Hex(payload));
            count++;
        }
        log.WriteLine("done " + DateTime.Now.ToString("HH:mm:ss.fff") + " packets=" + count);
        log.Close();
        sock.Close();
    }

    static string LocalIp()
    {
        foreach (var ni in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
        {
            if (ni.OperationalStatus != System.Net.NetworkInformation.OperationalStatus.Up) continue;
            foreach (var a in ni.GetIPProperties().UnicastAddresses)
            {
                string s = a.Address.ToString();
                if (s.StartsWith("192.168.2.")) return s;
            }
        }
        return "0.0.0.0";
    }

    static string Hex(byte[] d)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < d.Length; i++)
        {
            sb.Append(d[i].ToString("X2"));
            sb.Append(' ');
            if ((i + 1) % 16 == 0 && i + 1 < d.Length) sb.Append("\n   ");
        }
        return sb.ToString();
    }
}
