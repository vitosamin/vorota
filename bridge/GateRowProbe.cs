using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateRowProbe
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004, KEYUP = 0x0002;
    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero, access = IntPtr.Zero;
    static System.Collections.Generic.List<IntPtr> wins = new System.Collections.Generic.List<IntPtr>();

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        wins.Add(h);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        if (C(h).Contains("MSFlexGrid")) grid = h;
        return true;
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(120);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(220);
    }

    static void Dump(string tag)
    {
        wins.Clear();
        EnumWindows(Top, IntPtr.Zero);
        foreach (var h in wins)
        {
            if (h == access) continue;
            log.WriteLine(tag + " WIN class=" + C(h) + " text=[" + T(h) + "]");
            EnumChildWindows(h, (ch, l) => { log.WriteLine("    child class=" + C(ch) + " text=[" + T(ch) + "]"); return true; }, IntPtr.Zero);
        }
    }

    static int Main(string[] args)
    {
        int row = args.Length > 0 ? int.Parse(args[0]) : 1;
        log = new StreamWriter(@"C:\Users\Public\gate_rowprobe.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero) { log.WriteLine("no grid"); log.Close(); return 2; }
        RECT gr; GetWindowRect(grid, out gr);
        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);
        int y = gr.Top + 27 + (row - 1) * 15;
        Click(gr.Left + 60, y);
        log.WriteLine("single click row=" + row + " y=" + y);
        Dump("after-single");
        // double click
        SetCursorPos(gr.Left + 60, y); System.Threading.Thread.Sleep(100);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(40); mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(40); mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(1500);
        log.WriteLine("double click row=" + row);
        Dump("after-double");
        // escape
        keybd_event(0x1B, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(60); keybd_event(0x1B, 0, KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(500);
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
