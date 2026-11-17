using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateState
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);

    struct RECT { public int Left, Top, Right, Bottom; }
    static StreamWriter log;
    static uint targetPid;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        RECT r; GetWindowRect(h, out r);
        log.WriteLine("top h=" + h + " class=" + C(h) + " text=[" + T(h) + "] enabled=" + IsWindowEnabled(h)
            + " visible=" + IsWindowVisible(h) + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom
            + " foreground=" + (h == GetForegroundWindow()));
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        log.WriteLine("   child h=" + h + " class=" + C(h) + " text=[" + T(h) + "] enabled=" + IsWindowEnabled(h));
        return true;
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_state.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        log.WriteLine("pid=" + targetPid + " foreground=" + GetForegroundWindow());
        EnumWindows(Top, IntPtr.Zero);
        // children of the access window and of any dialog
        IntPtr access = IntPtr.Zero, dlg = IntPtr.Zero;
        EnumWindows((h, l) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid != targetPid) return true;
            string t = T(h);
            if (t.Contains("Управление точками доступа")) access = h;
            if (C(h) == "#32770") dlg = h;
            return true;
        }, IntPtr.Zero);
        if (access != IntPtr.Zero) { log.WriteLine("--- access children ---"); EnumChildWindows(access, Child, IntPtr.Zero); }
        if (dlg != IntPtr.Zero) { log.WriteLine("--- dialog children ---"); EnumChildWindows(dlg, Child, IntPtr.Zero); }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
