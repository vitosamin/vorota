using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;

/// <summary>Сниффер: пишет TCP-трафик на заданном порту (1917) и по IP-фильтру.
/// Запуск: GateSniff2.exe <секунд> <порт> <ip-фильтр> <файл></summary>
class GateSniff2
{
    static void Main(string[] args)
    {
        int seconds = args.Length > 0 ? int.Parse(args[0]) : 25;
        int port = args.Length > 1 ? int.Parse(args[1]) : 1917;
        string ipFilter = args.Length > 2 ? args[2] : "";
        string outPath = args.Length > 3 ? args[3] : @"C:\Users\Public\sniff2.txt";

        var log = new StreamWriter(outPath, false, new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " port=" + port + " ip=" + ipFilter);

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
            int sport = (buf[ihl] << 8) | buf[ihl + 1];
            int dport = (buf[ihl + 2] << 8) | buf[ihl + 3];

            bool match = (sport == port || dport == port);
            if (!match && ipFilter.Length > 0 && (src.StartsWith(ipFilter) || dst.StartsWith(ipFilter))) match = true;
            if (!match) continue;

            int len, hdr;
            if (proto == 17) { len = ((buf[ihl + 4] << 8) | buf[ihl + 5]) - 8; hdr = ihl + 8; }
            else if (proto == 6)
            {
                int doff = (buf[ihl + 12] >> 4) * 4;
                int total = (buf[2] << 8) | buf[3];
                len = total - ihl - doff;
                hdr = ihl + doff;
            }
            else continue;
            if (len < 0) continue;

            string payload = "";
            if (len > 0 && hdr + len <= n)
            {
                // пробуем как текст, иначе hex
                bool text = true;
                for (int i = 0; i < len; i++)
                {
                    byte b = buf[hdr + i];
                    if (b == 0) { text = false; break; }
                }
                if (text) payload = Encoding.UTF8.GetString(buf, hdr, len);
                else payload = Hex(buf, hdr, len);
            }
            log.WriteLine(DateTime.Now.ToString("HH:mm:ss.fff") + " " + src + ":" + sport + " -> " + dst + ":" + dport + " len=" + len);
            if (payload.Length > 0) log.WriteLine("   " + payload.Replace("\r", "\\r").Replace("\n", "\\n"));
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

    static string Hex(byte[] d, int off, int len)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < len; i++)
        {
            sb.Append(d[off + i].ToString("X2"));
            sb.Append(' ');
            if ((i + 1) % 16 == 0 && i + 1 < len) sb.Append("\n   ");
        }
        return sb.ToString();
    }
}
