using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateClose
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    static StreamWriter log;
    static uint pid;
    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }

    static bool Cb(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        string t = T(h);
        if (t.Length > 0) log.WriteLine("win: " + t + " visible=" + IsWindowVisible(h));
        if (t.Contains("Настройка реакций"))
        {
            log.WriteLine("closing: " + t);
            PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); // WM_CLOSE
        }
        return true;
    }

    static void Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_close.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return; }
        pid = (uint)ps[0].Id;
        EnumWindows(Cb, IntPtr.Zero);
        log.WriteLine("done");
        log.Close();
    }
}
