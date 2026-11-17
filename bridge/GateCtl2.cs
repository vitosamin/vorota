using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateCtl2
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);

    struct RECT { public int Left, Top, Right, Bottom; }
    static StreamWriter log;
    static uint targetPid;
    static IntPtr access = IntPtr.Zero, grid = IntPtr.Zero, openBtn = IntPtr.Zero;
    static System.Collections.Generic.List<IntPtr> dialogs = new System.Collections.Generic.List<IntPtr>();

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        if (C(h) == "#32770") dialogs.Add(h);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Contains("Открыть дверь")) openBtn = h;
        return true;
    }

    static void DumpDialogs()
    {
        foreach (var d in dialogs)
        {
            log.WriteLine("DIALOG h=" + d + " class=" + C(d) + " text=[" + T(d) + "] enabled=" + IsWindowEnabled(d));
            EnumChildWindows(d, (ch, l) => { log.WriteLine("   dlg child class=" + C(ch) + " text=[" + T(ch) + "]"); return true; }, IntPtr.Zero);
        }
    }

    static void DumpAll()
    {
        EnumWindows((h, l) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid != targetPid) return true;
            RECT r; GetWindowRect(h, out r);
            log.WriteLine("WIN class=" + C(h) + " text=[" + T(h) + "] enabled=" + IsWindowEnabled(h) + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);
            return true;
        }, IntPtr.Zero);
    }

    static void PostClick(IntPtr h, int cx, int cy)
    {
        IntPtr lp = (IntPtr)((cy << 16) | (cx & 0xFFFF));
        PostMessage(h, 0x0201, (IntPtr)1, lp);
        System.Threading.Thread.Sleep(60);
        PostMessage(h, 0x0202, IntPtr.Zero, lp);
        System.Threading.Thread.Sleep(200);
    }

    static void PostKey(IntPtr h, byte vk)
    {
        PostMessage(h, 0x0100, (IntPtr)vk, IntPtr.Zero);
        System.Threading.Thread.Sleep(40);
        PostMessage(h, 0x0101, (IntPtr)vk, IntPtr.Zero);
        System.Threading.Thread.Sleep(90);
    }

    static int Main(string[] args)
    {
        string mode = args.Length > 0 ? args[0] : "test";
        int row = args.Length > 1 ? int.Parse(args[1]) : 0;
        log = new StreamWriter(@"C:\Users\Public\gate_ctl2.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " mode=" + mode + " row=" + row);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " grid=" + grid + " openBtn=" + openBtn + " enabled=" + (openBtn != IntPtr.Zero ? IsWindowEnabled(openBtn).ToString() : "-"));
        if (access == IntPtr.Zero || grid == IntPtr.Zero || openBtn == IntPtr.Zero) { log.WriteLine("missing windows"); log.Close(); return 2; }

        RECT br; GetWindowRect(openBtn, out br);
        int bx = (br.Right - br.Left) / 2, by = (br.Bottom - br.Top) / 2;

        if (mode == "test")
        {
            log.WriteLine("clicking OPEN without selection");
            PostClick(openBtn, bx, by);
            System.Threading.Thread.Sleep(1500);
            dialogs.Clear();
            EnumWindows(Top, IntPtr.Zero);
            DumpDialogs();
            log.WriteLine("--- all windows ---");
            DumpAll();
        }
        else if (mode == "open")
        {
            log.WriteLine("selecting row " + row + " via keys");
            for (int i = 0; i < 40; i++) PostKey(grid, 0x26); // VK_UP
            for (int i = 0; i < row - 1; i++) PostKey(grid, 0x28); // VK_DOWN
            log.WriteLine("keys done " + DateTime.Now.ToString("HH:mm:ss.fff"));
            log.WriteLine("clicking OPEN");
            PostClick(openBtn, bx, by);
            log.WriteLine("clicked OPEN at " + DateTime.Now.ToString("HH:mm:ss.fff"));
            System.Threading.Thread.Sleep(2000);
            dialogs.Clear();
            EnumWindows(Top, IntPtr.Zero);
            DumpDialogs();
        }
        else if (mode == "close")
        {
            log.WriteLine("closing dialogs");
            dialogs.Clear();
            EnumWindows(Top, IntPtr.Zero);
            foreach (var d in dialogs)
            {
                EnumChildWindows(d, (ch, l) => {
                    if (C(ch) == "Button") { PostClick(ch, 20, 12); log.WriteLine("clicked dialog button " + T(ch)); }
                    return true;
                }, IntPtr.Zero);
            }
        }
        log.WriteLine("done " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.Close();
        return 0;
    }
}
