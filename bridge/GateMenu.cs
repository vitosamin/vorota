using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

/// <summary>Нажимает пункт меню GateTerm по его id (WM_COMMAND главному окну).
/// Пишет C:\Users\Public\gate_menu.txt.
///   41 — «Передача ключей в контроллеры»
///   42 — «Очистка банков ключей контроллеров»
///   40 — «Передача настроек в контроллеры»
///   28 — «Пользователи»</summary>
class GateMenu
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    static uint pid;
    static IntPtr main = IntPtr.Zero;
    static StreamWriter log;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Find(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p == pid && T(h).Contains("GATE Terminal")) main = h;
        return true;
    }

    static bool DumpWin(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p == pid && IsWindowVisible(h)) log.WriteLine("  win class=" + C(h) + " text=[" + T(h) + "]");
        return true;
    }

    static int Main(string[] args)
    {
        int id = args.Length > 0 ? int.Parse(args[0]) : 41;
        log = new StreamWriter(@"C:\Users\Public\gate_menu.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        pid = (uint)ps[0].Id;
        EnumWindows(Find, IntPtr.Zero);
        log.WriteLine("main=" + main + " menuId=" + id);
        if (main == IntPtr.Zero) { log.WriteLine("main window not found"); log.Close(); return 1; }
        bool sent = PostMessage(main, 0x0111, (IntPtr)id, IntPtr.Zero);
        log.WriteLine("PostMessage=" + sent + " " + DateTime.Now.ToString("HH:mm:ss"));
        Thread.Sleep(12000);
        log.WriteLine("after " + DateTime.Now.ToString("HH:mm:ss"));
        EnumWindows(DumpWin, IntPtr.Zero);
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
