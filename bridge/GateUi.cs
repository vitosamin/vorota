using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

/// <summary>Разведка интерфейса GateTerm: окна, элементы управления, меню.
/// Пишет C:\Users\Public\gate_ui.txt. Только чтение, ничего не нажимает.</summary>
class GateUi
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetMenu(IntPtr h);
    [DllImport("user32.dll")] static extern int GetMenuItemCount(IntPtr m);
    [DllImport("user32.dll")] static extern IntPtr GetSubMenu(IntPtr m, int pos);
    [DllImport("user32.dll")] static extern uint GetMenuItemID(IntPtr m, int pos);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetMenuString(IntPtr m, uint item, StringBuilder s, int n, uint flags);

    static StreamWriter log;
    static uint pid;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static void DumpMenu(IntPtr m, string prefix)
    {
        int n = GetMenuItemCount(m);
        for (int i = 0; i < n; i++)
        {
            var sb = new StringBuilder(512);
            GetMenuString(m, (uint)i, sb, 512, 0x400);   // MF_BYPOSITION
            IntPtr sub = GetSubMenu(m, i);
            uint id = GetMenuItemID(m, i);
            log.WriteLine(prefix + "[" + i + "] id=" + id + " text=[" + sb + "]" + (sub != IntPtr.Zero ? " SUB" : ""));
            if (sub != IntPtr.Zero) DumpMenu(sub, prefix + "   ");
        }
    }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        log.WriteLine("WIN h=" + h + " class=" + C(h) + " vis=" + IsWindowVisible(h) + " text=[" + T(h) + "]");
        EnumChildWindows(h, Child, IntPtr.Zero);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        log.WriteLine("    ctrl h=" + h + " id=" + GetDlgCtrlID(h) + " class=" + C(h)
                      + " vis=" + IsWindowVisible(h) + " text=[" + T(h) + "]");
        return true;
    }

    static IntPtr main = IntPtr.Zero;
    static bool FindMain(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p == pid && T(h).Contains("GATE Terminal")) main = h;
        return true;
    }

    static int Main(string[] args)
    {
        log = new StreamWriter(@"C:\Users\Public\gate_ui.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        pid = (uint)ps[0].Id;
        log.WriteLine("pid=" + pid);
        EnumWindows(Top, IntPtr.Zero);
        EnumWindows(FindMain, IntPtr.Zero);
        if (main != IntPtr.Zero)
        {
            IntPtr m = GetMenu(main);
            log.WriteLine("main=" + main + " menu=" + m);
            if (m != IntPtr.Zero) DumpMenu(m, "  ");
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
