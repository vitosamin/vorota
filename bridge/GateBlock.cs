using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateBlock
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
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero, access = IntPtr.Zero, lockBtn = IntPtr.Zero, unlockBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        if (T(h).Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton"))
        {
            if (t.Contains("Заблокировать")) lockBtn = h;
            else if (t.Contains("Разблокировать")) unlockBtn = h;
        }
        return true;
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(120);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(250);
    }

    static void ClickBtn(IntPtr b, string name)
    {
        RECT r; GetWindowRect(b, out r);
        log.WriteLine("click " + name + " enabled=" + IsWindowEnabled(b));
        Click((r.Left + r.Right) / 2, (r.Top + r.Bottom) / 2);
        System.Threading.Thread.Sleep(700);
    }

    static int Main(string[] args)
    {
        int row = args.Length > 0 ? int.Parse(args[0]) : 7;
        log = new StreamWriter(@"C:\Users\Public\gate_block.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " row=" + row);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero || lockBtn == IntPtr.Zero || unlockBtn == IntPtr.Zero)
        { log.WriteLine("grid=" + grid + " lock=" + lockBtn + " unlock=" + unlockBtn); log.Close(); return 2; }
        RECT gr; GetWindowRect(grid, out gr);
        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);
        int y = gr.Top + 42 + 16 * row;
        Click(gr.Left + 60, y);
        log.WriteLine("selected row=" + row + " y=" + y);
        ClickBtn(lockBtn, "Заблокировать");
        log.WriteLine("after lock: unlock enabled=" + IsWindowEnabled(unlockBtn) + " at " + DateTime.Now.ToString("HH:mm:ss.fff"));
        ClickBtn(unlockBtn, "Разблокировать");
        log.WriteLine("after unlock: unlock enabled=" + IsWindowEnabled(unlockBtn) + " at " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
