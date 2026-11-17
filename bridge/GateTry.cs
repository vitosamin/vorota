using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

class GateTry
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr GetFocus();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);

    const uint WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, BM_CLICK = 0x00F5;
    const int VK_SPACE = 0x20, VK_RETURN = 0x0D;
    static StreamWriter log;
    static uint pid;
    static IntPtr access = IntPtr.Zero, openBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        if (T(h).Contains("Управление точками")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("CommandButton") && t.Contains("Открыть")) openBtn = h;
        return true;
    }

    static void Main(string[] args)
    {
        string method = args.Length > 0 ? args[0] : "bm";
        log = new StreamWriter(@"C:\Users\Public\gate_try.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return; }
        pid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " btn=" + openBtn + " method=" + method);
        if (access == IntPtr.Zero || openBtn == IntPtr.Zero) { log.WriteLine("missing"); log.Close(); return; }
        BringWindowToTop(access);
        SetForegroundWindow(access);
        Thread.Sleep(300);
        IntPtr focus = GetFocus();
        log.WriteLine("focus=" + focus + " class=" + C(focus) + " title=[" + T(focus) + "]");
        switch (method)
        {
            case "bm":
                SendMessage(openBtn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
                log.WriteLine("BM_CLICK sent");
                break;
            case "space":
                SendMessage(openBtn, WM_KEYDOWN, (IntPtr)VK_SPACE, IntPtr.Zero);
                Thread.Sleep(80);
                SendMessage(openBtn, WM_KEYUP, (IntPtr)VK_SPACE, IntPtr.Zero);
                log.WriteLine("SPACE sent to button");
                break;
            case "enter":
                SendMessage(access, WM_KEYDOWN, (IntPtr)VK_RETURN, IntPtr.Zero);
                Thread.Sleep(80);
                SendMessage(access, WM_KEYUP, (IntPtr)VK_RETURN, IntPtr.Zero);
                log.WriteLine("ENTER sent to form");
                break;
        }
        Thread.Sleep(1500);
        log.WriteLine("done at " + DateTime.Now.ToString("HH:mm:ss"));
        log.Close();
    }
}
