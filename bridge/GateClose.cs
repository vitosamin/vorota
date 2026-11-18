using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

/// <summary>Находит окно GateTerm по части заголовка и нажимает в нём кнопку
/// по части надписи. Пишет C:\Users\Public\gate_close.txt.
///   GateClose.exe "Передача ключей" Выход
///   GateClose.exe GateTerm ОК
/// </summary>
class GateClose
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    const uint BM_CLICK = 0x00F5;

    static string wantWin, wantBtn;
    static IntPtr found = IntPtr.Zero, btn = IntPtr.Zero;
    static StreamWriter log;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }

    static bool FindWin(IntPtr h, IntPtr l)
    {
        if (!IsWindowVisible(h)) return true;
        if (T(h).Contains(wantWin)) { found = h; EnumChildWindows(h, FindBtn, IntPtr.Zero); }
        return true;
    }

    static bool FindBtn(IntPtr h, IntPtr l)
    {
        if (T(h).Contains(wantBtn)) btn = h;
        return true;
    }

    static int Main(string[] args)
    {
        log = new StreamWriter(@"C:\Users\Public\gate_close.txt", true, Encoding.UTF8);
        log.AutoFlush = true;
        if (args.Length < 2) { log.WriteLine("usage: GateClose <window> <button>"); log.Close(); return 1; }
        wantWin = args[0]; wantBtn = args[1];
        EnumWindows(FindWin, IntPtr.Zero);
        log.WriteLine(DateTime.Now.ToString("HH:mm:ss") + " ищу окно [" + wantWin + "] кнопку [" + wantBtn + "]");
        if (found == IntPtr.Zero) { log.WriteLine("  окно не найдено"); log.Close(); return 1; }
        if (btn == IntPtr.Zero) { log.WriteLine("  окно найдено (" + found + "), кнопка не найдена"); log.Close(); return 1; }
        SendMessage(btn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
        log.WriteLine("  нажато, окно=" + found + " кнопка=" + btn);
        Thread.Sleep(1500);
        log.Close();
        return 0;
    }
}
