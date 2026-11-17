using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

class GatePress
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern long GetWindowLong(IntPtr h, int idx);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004, WM_COMMAND = 0x0111, BN_CLICKED = 0;
    static StreamWriter log;
    static uint pid;
    static IntPtr access = IntPtr.Zero, grid = IntPtr.Zero, openBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        string t = T(h);
        if (t.Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Contains("Открыть")) openBtn = h;
        return true;
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); Thread.Sleep(60);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); Thread.Sleep(30);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); Thread.Sleep(120);
    }

    static void Main(string[] args)
    {
        int row = args.Length > 0 ? int.Parse(args[0]) : 0;
        log = new StreamWriter(@"C:\Users\Public\gate_press.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return; }
        pid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " grid=" + grid + " openBtn=" + openBtn);
        if (access == IntPtr.Zero || openBtn == IntPtr.Zero) { log.WriteLine("missing"); log.Close(); return; }
        log.WriteLine("access style=0x" + GetWindowLong(access, -16).ToString("X") + " enabled=" + IsWindowEnabled(access));
        log.WriteLine("btn enabled=" + IsWindowEnabled(openBtn) + " ctrlId=" + GetDlgCtrlID(openBtn));
        if (row > 0 && grid != IntPtr.Zero)
        {
            RECT gr; GetWindowRect(grid, out gr);
            int y = gr.Top + 42 + 16 * row;
            log.WriteLine("select row " + row + " at y=" + y + " grid=" + gr.Left + "," + gr.Top);
            Click(gr.Left + 60, y);
            Thread.Sleep(250);
            Click(gr.Left + 60, y);
            Thread.Sleep(400);
        }
        int cid = GetDlgCtrlID(openBtn);
        IntPtr wparam = (IntPtr)((BN_CLICKED << 16) | (cid & 0xFFFF));
        bool ok = PostMessage(access, WM_COMMAND, wparam, openBtn);
        log.WriteLine("WM_COMMAND posted=" + ok + " wparam=0x" + ((long)wparam).ToString("X"));
        Thread.Sleep(1500);
        log.WriteLine("done");
        log.Close();
    }
}
