using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateExit
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint targetPid;
    static IntPtr access = IntPtr.Zero, exitBtn = IntPtr.Zero;

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
        if (C(h).Contains("CommandButton") && T(h).Trim() == "Выход") exitBtn = h;
        return true;
    }

    static int Main(string[] args)
    {
        log = new StreamWriter(@"C:\Users\Public\gate_exit.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " session=" + Process.GetCurrentProcess().SessionId);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " exitBtn=" + exitBtn);
        if (access == IntPtr.Zero) { log.WriteLine("no access window"); log.Close(); return 2; }
        IntPtr fg = GetForegroundWindow();
        log.WriteLine("foreground before=" + fg + " text=[" + T(fg) + "]");
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        ShowWindow(access, 5);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(600);
        fg = GetForegroundWindow();
        log.WriteLine("foreground after=" + fg + " text=[" + T(fg) + "]");
        if (exitBtn != IntPtr.Zero)
        {
            RECT r; GetWindowRect(exitBtn, out r);
            int x = (r.Left + r.Right) / 2, y = (r.Top + r.Bottom) / 2;
            log.WriteLine("clicking Выход at " + x + "," + y);
            SetCursorPos(x, y);
            System.Threading.Thread.Sleep(200);
            mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(80);
            mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(1200);
        }
        bool stillThere = false;
        EnumWindows((h, l) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid == targetPid && T(h).Contains("Управление точками доступа")) stillThere = true;
            return true;
        }, IntPtr.Zero);
        log.WriteLine("access window still present=" + stillThere + " at " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
