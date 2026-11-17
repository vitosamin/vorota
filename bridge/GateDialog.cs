using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateDialog
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, StringBuilder l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    static StreamWriter log;
    static uint targetPid;
    static IntPtr mainWnd = IntPtr.Zero;
    static System.Collections.Generic.List<IntPtr> tops = new System.Collections.Generic.List<IntPtr>();

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("GATE Terminal")) mainWnd = h;
        tops.Add(h);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        log.WriteLine("    ctrl class=" + c + " text=[" + t + "] visible=" + IsWindowVisible(h));
        if (c.Contains("ComboBox") || c.Contains("ListBox"))
        {
            int cnt = (int)SendMessage(h, 0x0146, IntPtr.Zero, IntPtr.Zero); // CB_GETCOUNT
            log.WriteLine("      items=" + cnt);
            for (int i = 0; i < cnt && i < 40; i++)
            {
                var sb = new StringBuilder(512);
                SendMessage(h, 0x0148, (IntPtr)i, sb); // CB_GETLBTEXT
                log.WriteLine("      item[" + i + "]=" + sb.ToString());
            }
        }
        return true;
    }

    static void DumpTops()
    {
        tops.Clear();
        EnumWindows(Top, IntPtr.Zero);
        foreach (var h in tops)
        {
            if (!IsWindowVisible(h)) continue;
            log.WriteLine("WIN class=" + C(h) + " text=[" + T(h) + "]");
            EnumChildWindows(h, Child, IntPtr.Zero);
        }
    }

    static int Main(string[] args)
    {
        int menuId = args.Length > 0 ? int.Parse(args[0]) : 13;
        log = new StreamWriter(@"C:\Users\Public\gate_dialog.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("main=" + mainWnd + " menuId=" + menuId);
        log.WriteLine("--- before ---");
        DumpTops();
        if (mainWnd != IntPtr.Zero)
        {
            PostMessage(mainWnd, 0x0111, (IntPtr)menuId, IntPtr.Zero);
            System.Threading.Thread.Sleep(3000);
        }
        log.WriteLine("--- after ---");
        DumpTops();
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
