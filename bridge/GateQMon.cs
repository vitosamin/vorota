using System;
using System.Collections.Generic;
using System.Data.OleDb;
using System.IO;
using System.Text;
using System.Threading;

/// <summary>Мониторит таблицу CommandQuetch с точностью до миллисекунд.
/// Только чтение. Сборка x86 (нужен Jet 4.0).</summary>
class GateQMon
{
    static void Main(string[] args)
    {
        int seconds = args.Length > 0 ? int.Parse(args[0]) : 25;
        string outPath = args.Length > 1 ? args[1] : @"C:\Users\Public\qmon.txt";
        var log = new StreamWriter(outPath, false, new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff"));

        string cs = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\\GATE\\Server\\config.mdb;"
                  + "Jet OLEDB:System database=C:\\GATE\\Server\\Gate.mdw;User ID=master;Password=masterio0;";
        string prev = "";
        var sw = System.Diagnostics.Stopwatch.StartNew();
        while (sw.Elapsed.TotalSeconds < seconds)
        {
            try
            {
                using (var conn = new OleDbConnection(cs))
                {
                    conn.Open();
                    using (var cmd = new OleDbCommand("SELECT Ptr, Code, PortPtr, Addr FROM CommandQuetch ORDER BY Ptr", conn))
                    using (var r = cmd.ExecuteReader())
                    {
                        var sb = new StringBuilder();
                        while (r.Read())
                        {
                            sb.Append('[').Append(r[0]).Append(",code=").Append(r[1])
                              .Append(",port=").Append(r[2]).Append(",addr=").Append(r[3]).Append(']');
                        }
                        string cur = sb.ToString();
                        if (cur != prev)
                        {
                            log.WriteLine(DateTime.Now.ToString("HH:mm:ss.fff") + "  queue: " + (cur.Length == 0 ? "(пусто)" : cur));
                            prev = cur;
                        }
                    }
                }
            }
            catch (Exception e)
            {
                log.WriteLine(DateTime.Now.ToString("HH:mm:ss.fff") + "  err " + e.Message);
            }
            Thread.Sleep(15);
        }
        log.WriteLine("done " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.Close();
    }
}
