using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateGridClip
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool OpenClipboard(IntPtr h);
    [DllImport("user32.dll")] static extern bool CloseClipboard();
    [DllImport("user32.dll")] static extern IntPtr GetClipboardData(uint fmt);
    [DllImport("kernel32.dll")] static extern IntPtr GlobalLock(IntPtr h);
    [DllImport("kernel32.dll")] static extern bool GlobalUnlock(IntPtr h);

    struct RECT { public int Left, Top, Right, Bottom; }
    const byte VK_SHIFT = 0x10, VK_CONTROL = 0x11;
    const uint KEYEVENTF_KEYUP = 0x0002;

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

    static void Click(int x, int y)
    {
        IntPtr lp = (IntPtr)((y << 16) | (x & 0xFFFF));
        PostMessage(grid, 0x0201, (IntPtr)1, lp);
        System.Threading.Thread.Sleep(120);
        PostMessage(grid, 0x0202, IntPtr.Zero, lp);
        System.Threading.Thread.Sleep(200);
    }

    static string ClipboardText()
    {
        if (!OpenClipboard(IntPtr.Zero)) return "<clipboard busy>";
        try
        {
            IntPtr h = GetClipboardData(13); // CF_UNICODETEXT
            if (h == IntPtr.Zero)
            {
                h = GetClipboardData(1); // CF_TEXT
                if (h == IntPtr.Zero) return "<empty>";
                IntPtr p = GlobalLock(h);
                string s = Marshal.PtrToStringAnsi(p);
                GlobalUnlock(h);
                return s ?? "<null>";
            }
            IntPtr pu = GlobalLock(h);
            string su = Marshal.PtrToStringUni(pu);
            GlobalUnlock(h);
            return su ?? "<null>";
        }
        finally { CloseClipboard(); }
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_gridclip.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero) { log.WriteLine("no grid"); log.Close(); return 2; }
        RECT r; GetWindowRect(grid, out r);
        log.WriteLine("grid=" + grid + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);

        // focus the grid window so keyboard goes to it
        IntPtr fg = GetForegroundWindow();
        uint fgThread = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myThread = GetCurrentThreadId();
        AttachThreadInput(myThread, fgThread, true);
        SetForegroundWindow(grid);
        AttachThreadInput(myThread, fgThread, false);
        System.Threading.Thread.Sleep(400);

        int height = r.Bottom - r.Top;
        Click(60, 24);
        keybd_event(VK_SHIFT, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(150);
        Click(60, Math.Min(height - 8, 340));
        keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(300);

        keybd_event(VK_CONTROL, 0, 0, IntPtr.Zero);
        keybd_event(0x43, 0, 0, IntPtr.Zero); // C
        System.Threading.Thread.Sleep(60);
        keybd_event(0x43, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(600);

        log.WriteLine("--- clipboard ---");
        log.WriteLine(ClipboardText());
        log.WriteLine("--- end ---");
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
