using System;
using System.IO;
using System.Text;
using System.Threading;

/// <summary>Замеряет частоту обращений к базе Gate по времени изменения lock-файла.
/// Только чтение метаданных файла.</summary>
class GateDbPulse
{
    static void Main(string[] args)
    {
        int seconds = args.Length > 0 ? int.Parse(args[0]) : 15;
        string outPath = args.Length > 1 ? args[1] : @"C:\Users\Public\pulse.txt";
        string[] files = { @"C:\GATE\Server\config.ldb", @"C:\GATE\Server\config.mdb" };

        var log = new StreamWriter(outPath, false, new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff"));

        var last = new DateTime[files.Length];
        for (int i = 0; i < files.Length; i++)
            try { last[i] = File.GetLastWriteTimeUtc(files[i]); } catch { last[i] = DateTime.MinValue; }

        var sw = System.Diagnostics.Stopwatch.StartNew();
        int ticks = 0;
        while (sw.Elapsed.TotalSeconds < seconds)
        {
            for (int i = 0; i < files.Length; i++)
            {
                try
                {
                    DateTime t = File.GetLastWriteTimeUtc(files[i]);
                    if (t != last[i])
                    {
                        log.WriteLine(DateTime.Now.ToString("HH:mm:ss.fff") + "  " + Path.GetFileName(files[i]) + "  +" + t.ToString("HH:mm:ss.fff"));
                        last[i] = t;
                        ticks++;
                    }
                }
                catch { }
            }
            Thread.Sleep(5);
        }
        log.WriteLine("done ticks=" + ticks + " " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.Close();
    }
}
