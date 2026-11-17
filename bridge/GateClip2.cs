using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateClip2
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags, uint dx, uint dy, uint data, IntPtr extra);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool OpenClipboard(IntPtr h);
    [DllImport("user32.dll")] static extern bool CloseClipboard();
    [DllImport("user32.dll")] static extern IntPtr GetClipboardData(uint fmt);
    [DllImport("kernel32.dll")] static extern IntPtr GlobalLock(IntPtr h);
    [DllImport("kernel32.dll")] static extern bool GlobalUnlock(IntPtr h);

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004;
    const uint KEYEVENTF_KEYUP = 0x0002;
    const byte VK_SHIFT = 0x10, VK_CONTROL = 0x11;

    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero, access = IntPtr.Zero;

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
        if (C(h).Contains("MSFlexGrid")) grid = h;
        return true;
    }

    static void RealClick(int x, int y)
    {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(120);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(200);
    }

    static string Clip()
    {
        if (!OpenClipboard(IntPtr.Zero)) return "<busy>";
        try
        {
            IntPtr h = GetClipboardData(13);
            if (h != IntPtr.Zero) { IntPtr p = GlobalLock(h); string s = Marshal.PtrToStringUni(p); GlobalUnlock(h); return s ?? "<null>"; }
            h = GetClipboardData(1);
            if (h != IntPtr.Zero) { IntPtr p = GlobalLock(h); string s = Marshal.PtrToStringAnsi(p); GlobalUnlock(h); return s ?? "<null>"; }
            return "<empty>";
        }
        finally { CloseClipboard(); }
    }

    static void Focus(IntPtr h)
    {
        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(h);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_clip2.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (access == IntPtr.Zero || grid == IntPtr.Zero) { log.WriteLine("access=" + access + " grid=" + grid); log.Close(); return 2; }
        RECT gr; GetWindowRect(grid, out gr);
        log.WriteLine("access=" + access + " grid=" + grid + " gridrect=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom);
        Focus(access);
        int x = gr.Left + 60;
        int y1 = gr.Top + 26;
        int y2 = gr.Bottom - 10;
        log.WriteLine("click1=" + x + "," + y1 + " click2=" + x + "," + y2);
        RealClick(x, y1);
        keybd_event(VK_SHIFT, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(150);
        RealClick(x, y2);
        keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(300);
        keybd_event(VK_CONTROL, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        keybd_event(0x43, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        keybd_event(0x43, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(800);
        string c1 = Clip();
        log.WriteLine("--- clipboard after shift-select ---");
        log.WriteLine(c1);
        // try ctrl+a then ctrl+c
        keybd_event(VK_CONTROL, 0, 0, IntPtr.Zero);
        keybd_event(0x41, 0, 0, IntPtr.Zero);
        keybd_event(0x41, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(300);
        keybd_event(VK_CONTROL, 0, 0, IntPtr.Zero);
        keybd_event(0x43, 0, 0, IntPtr.Zero);
        keybd_event(0x43, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(800);
        log.WriteLine("--- clipboard after ctrl+a ctrl+c ---");
        log.WriteLine(Clip());
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
