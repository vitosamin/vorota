using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateGridRead
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, StringBuilder l);

    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        if (T(h).Contains("Управление точками доступа")) EnumChildWindows(h, Child, IntPtr.Zero);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        if (C(h).Contains("MSFlexGrid")) grid = h;
        return true;
    }

    static string CellText()
    {
        var sb = new StringBuilder(512);
        SendMessage(grid, 0x000D, (IntPtr)512, sb); // WM_GETTEXT
        return sb.ToString();
    }

    static void Click(int x, int y)
    {
        IntPtr lp = (IntPtr)((y << 16) | (x & 0xFFFF));
        PostMessage(grid, 0x0201, (IntPtr)1, lp);
        System.Threading.Thread.Sleep(80);
        PostMessage(grid, 0x0202, IntPtr.Zero, lp);
        System.Threading.Thread.Sleep(160);
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_gridread.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero) { log.WriteLine("no grid"); log.Close(); return 2; }
        log.WriteLine("grid=" + grid);
        for (int y = 4; y <= 260; y += 15)
        {
            Click(60, y);
            log.WriteLine("y=" + y + " text=[" + CellText() + "]");
        }
        // ещё раз по колонке с адресом
        log.WriteLine("--- second column ---");
        for (int y = 4; y <= 120; y += 15)
        {
            Click(150, y);
            log.WriteLine("y=" + y + " text=[" + CellText() + "]");
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
