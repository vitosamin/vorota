using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateDoor
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
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004, KEYUP = 0x0002;
    const byte VK_CONTROL = 0x11, VK_HOME = 0x24, VK_DOWN = 0x28, VK_RETURN = 0x0D;

    static StreamWriter log;
    static uint targetPid;
    static IntPtr access = IntPtr.Zero, grid = IntPtr.Zero, openBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        if (C(h) == "#32770" && t.Contains("GateTerm")) log.WriteLine("DIALOG: " + DumpDialog(h));
        return true;
    }

    static string DumpDialog(IntPtr h)
    {
        var sb = new StringBuilder();
        EnumChildWindows(h, (ch, l) => { sb.Append("[" + C(ch) + ":" + T(ch) + "]"); return true; }, IntPtr.Zero);
        return sb.ToString();
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Contains("Открыть дверь")) openBtn = h;
        return true;
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(140);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(70);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(250);
    }

    static void Key(byte vk, bool ctrl)
    {
        if (ctrl) keybd_event(VK_CONTROL, 0, 0, IntPtr.Zero);
        keybd_event(vk, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(40);
        keybd_event(vk, 0, KEYUP, IntPtr.Zero);
        if (ctrl) keybd_event(VK_CONTROL, 0, KEYUP, IntPtr.Zero);
        System.Threading.Thread.Sleep(120);
    }

    static int Main(string[] args)
    {
        int steps = args.Length > 0 ? int.Parse(args[0]) : 0;
        bool pressOpen = args.Length > 1 && args[1] == "open";
        log = new StreamWriter(@"C:\Users\Public\gate_door.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now.ToString("HH:mm:ss.fff") + " steps=" + steps + " open=" + pressOpen);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (access == IntPtr.Zero || grid == IntPtr.Zero) { log.WriteLine("access=" + access + " grid=" + grid); log.Close(); return 2; }
        RECT gr, br;
        GetWindowRect(grid, out gr);
        log.WriteLine("grid=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom);

        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);

        Click(gr.Left + 60, gr.Top + 28);
        log.WriteLine("clicked first row " + DateTime.Now.ToString("HH:mm:ss.fff"));
        Key(VK_HOME, true);
        log.WriteLine("ctrl+home " + DateTime.Now.ToString("HH:mm:ss.fff"));
        for (int i = 0; i < steps; i++)
        {
            Key(VK_DOWN, false);
        }
        log.WriteLine("moved down " + steps + " at " + DateTime.Now.ToString("HH:mm:ss.fff"));

        if (pressOpen && openBtn != IntPtr.Zero)
        {
            GetWindowRect(openBtn, out br);
            Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
            log.WriteLine("clicked OPEN at " + DateTime.Now.ToString("HH:mm:ss.fff"));
        }
        System.Threading.Thread.Sleep(2500);
        log.WriteLine("--- windows after ---");
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("done " + DateTime.Now.ToString("HH:mm:ss.fff"));
        log.Close();
        return 0;
    }
}
