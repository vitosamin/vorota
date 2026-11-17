using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

/// <summary>Читает память процесса GateServ и выписывает строки по ключевым словам.
/// Только чтение: ReadProcessMemory, ничего не изменяется.</summary>
class GateMem
{
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
    [DllImport("kernel32.dll")] static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, IntPtr len);

    [StructLayout(LayoutKind.Sequential)]
    struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    const uint PROCESS_QUERY_INFORMATION = 0x0400;
    const uint PROCESS_VM_READ = 0x0010;
    const uint MEM_COMMIT = 0x1000;
    const uint PAGE_GUARD = 0x100;
    const uint PAGE_NOACCESS = 0x01;

    static readonly string[] Keys = {
        "CommandQuetch", "ControlPeriod", "PollingPeriod", "Period", "период", "Период",
        "команд", "Команд", "двер", "Двер", "открыт", "Открыт", "очеред", "Очеред",
        "Timer", "Interval", "интервал", "задержк", "OperEvent", "Outputs", "Output",
        "UPDATE", "SELECT", "INSERT", "config.mdb", "Gate.mdw", "masterio0"
    };

    static void Main(string[] args)
    {
        var log = new StreamWriter(@"C:\Users\Public\mem.txt", false, new UTF8Encoding(false));
        log.AutoFlush = true;
        var procs = System.Diagnostics.Process.GetProcessesByName(args.Length > 0 ? args[0] : "GateServ");
        if (procs.Length == 0) { log.WriteLine("процесс не найден"); log.Close(); return; }
        int pid = procs[0].Id;
        log.WriteLine("PID=" + pid + " start=" + DateTime.Now.ToString("HH:mm:ss"));

        IntPtr h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid);
        if (h == IntPtr.Zero) { log.WriteLine("OpenProcess не удалось, код=" + Marshal.GetLastWin32Error()); log.Close(); return; }

        var ascii = new Dictionary<string, int>();
        var wide = new Dictionary<string, int>();
        long addr = 0x10000;
        long scanned = 0, readTotal = 0;
        var buf = new byte[1 << 20];

        while (addr < 0x7FFFFFFF)
        {
            MEMORY_BASIC_INFORMATION mbi;
            IntPtr r = VirtualQueryEx(h, (IntPtr)addr, out mbi, (IntPtr)Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION)));
            if (r == IntPtr.Zero) break;
            long size = (long)mbi.RegionSize;
            if (size <= 0) break;

            bool ok = mbi.State == MEM_COMMIT
                      && (mbi.Protect & PAGE_NOACCESS) == 0
                      && (mbi.Protect & PAGE_GUARD) == 0;
            if (ok)
            {
                long left = size;
                long a = addr;
                while (left > 0)
                {
                    int chunk = (int)Math.Min(buf.Length, left);
                    int got;
                    if (ReadProcessMemory(h, (IntPtr)a, buf, chunk, out got) && got > 0)
                    {
                        readTotal += got;
                        ScanAscii(buf, got, ascii);
                        ScanWide(buf, got, wide);
                    }
                    a += chunk; left -= chunk;
                }
                scanned += size;
            }
            addr += size;
        }
        log.WriteLine("прочитано МБ=" + (readTotal / 1048576) + " регионов просканировано МБ=" + (scanned / 1048576));
        log.WriteLine("=== ASCII-строки (" + ascii.Count + ") ===");
        foreach (var kv in ascii) log.WriteLine(kv.Value + "\t" + kv.Key);
        log.WriteLine("=== UTF-16 строки (" + wide.Count + ") ===");
        foreach (var kv in wide) log.WriteLine(kv.Value + "\t" + kv.Key);
        log.WriteLine("done " + DateTime.Now.ToString("HH:mm:ss"));
        CloseHandle(h);
        log.Close();
    }

    static bool Interesting(string s)
    {
        foreach (string k in Keys) if (s.IndexOf(k, StringComparison.OrdinalIgnoreCase) >= 0) return true;
        return false;
    }

    static void ScanAscii(byte[] b, int n, Dictionary<string, int> found)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < n; i++)
        {
            byte c = b[i];
            if (c >= 0x20 && c < 0x7F) sb.Append((char)c);
            else
            {
                if (sb.Length >= 5)
                {
                    string s = sb.ToString();
                    if (Interesting(s))
                    {
                        int v; found.TryGetValue(s, out v); found[s] = v + 1;
                    }
                }
                sb.Length = 0;
            }
        }
    }

    static void ScanWide(byte[] b, int n, Dictionary<string, int> found)
    {
        var sb = new StringBuilder();
        for (int i = 0; i + 1 < n; i += 2)
        {
            byte lo = b[i], hi = b[i + 1];
            if (hi == 0 && ((lo >= 0x20 && lo < 0x7F) || lo >= 0x80))
            {
                sb.Append((char)lo);
            }
            else
            {
                if (sb.Length >= 5)
                {
                    string s = sb.ToString();
                    if (Interesting(s))
                    {
                        int v; found.TryGetValue(s, out v); found[s] = v + 1;
                    }
                }
                sb.Length = 0;
            }
        }
    }
}
