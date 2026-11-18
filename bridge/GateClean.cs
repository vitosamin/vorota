using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

/// <summary>Закрывает модальные окна GateTerm: системный диалог ошибки и
/// окно «Передача ключей в контроллеры». Без аргументов — чтобы не зависеть
/// от кодировки командной строки. Пишет C:\Users\Public\gate_clean.txt.</summary>
class GateClean
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    const uint BM_CLICK = 0x00F5;

    static uint pid;
    static StreamWriter log;
    static int closed = 0;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static IntPtr btnIn = IntPtr.Zero;
    static string btnWant = "";

    static bool PickBtn(IntPtr h, IntPtr l)
    {
        string t = T(h), c = C(h);
        if (c != "Button" && !c.Contains("CommandButton")) return true;
        if (btnWant.Length == 0 || t.Contains(btnWant)) btnIn = h;
        return true;
    }

    static bool Scan(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid || !IsWindowVisible(h)) return true;
        string t = T(h), c = C(h);
        if (c == "#32770")                       // системный диалог ошибки
        {
            btnWant = ""; btnIn = IntPtr.Zero;
            EnumChildWindows(h, PickBtn, IntPtr.Zero);
            if (btnIn != IntPtr.Zero)
            {
                log.WriteLine("диалог [" + t + "] → нажимаю кнопку");
                SendMessage(btnIn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
                closed++;
            }
        }
        else if (t.Contains("Передача ключей"))
        {
            btnWant = "Выход"; btnIn = IntPtr.Zero;
            EnumChildWindows(h, PickBtn, IntPtr.Zero);
            if (btnIn != IntPtr.Zero)
            {
                log.WriteLine("окно [" + t.Trim() + "] → нажимаю «Выход»");
                SendMessage(btnIn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
                closed++;
            }
        }
        return true;
    }

    static int Main(string[] args)
    {
        log = new StreamWriter(@"C:\Users\Public\gate_clean.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        pid = (uint)ps[0].Id;
        for (int pass = 0; pass < 3; pass++)
        {
            EnumWindows(Scan, IntPtr.Zero);
            Thread.Sleep(1200);
        }
        log.WriteLine("закрыто окон: " + closed);
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
