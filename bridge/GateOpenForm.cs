using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateOpenForm
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);

    static StreamWriter log;
    static uint targetPid;
    static IntPtr mainWnd = IntPtr.Zero;
    static bool accessOpen = false;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("GATE Terminal")) mainWnd = h;
        if (t.Contains("Управление точками доступа")) accessOpen = true;
        return true;
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_openform.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("main=" + mainWnd + " accessOpen=" + accessOpen);
        if (mainWnd != IntPtr.Zero && !accessOpen)
        {
            PostMessage(mainWnd, 0x0111, (IntPtr)83, IntPtr.Zero);
            log.WriteLine("posted menu 83");
            System.Threading.Thread.Sleep(3000);
            accessOpen = false;
            EnumWindows(Top, IntPtr.Zero);
            log.WriteLine("accessOpen now=" + accessOpen);
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
