using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

/// <summary>Рассылает ключи в контроллеры через меню GateTerm:
/// «Прием-передача» → «Передача ключей в контроллеры» (id=41),
/// в открывшемся окне ставит «Выбрать все» и жмёт «Выполнить».
/// Пишет C:\Users\Public\gate_keys.txt.
/// Параметр: число секунд ожидания после «Выполнить» (по умолчанию 30).</summary>
class GateKeys
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr h);

    const uint WM_COMMAND = 0x0111, BM_CLICK = 0x00F5, BM_SETCHECK = 0x00F1;
    const int BST_CHECKED = 1;
    const int MENU_TRANSFER_KEYS = 41;

    static uint pid;
    static IntPtr main = IntPtr.Zero, dlg = IntPtr.Zero;
    static IntPtr chkAll = IntPtr.Zero, btnRun = IntPtr.Zero, btnExit = IntPtr.Zero;
    static StreamWriter log;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool FindMain(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p == pid && T(h).Contains("GATE Terminal")) main = h;
        return true;
    }

    static bool FindDlg(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p == pid && T(h).Contains("Передача ключей")) dlg = h;
        return true;
    }

    static bool FindCtl(IntPtr h, IntPtr l)
    {
        string t = T(h);
        if (t.Contains("Выбрать все")) chkAll = h;
        if (t.Contains("Выполнить")) btnRun = h;
        if (t.Contains("Выход")) btnExit = h;
        return true;
    }

    static int Main(string[] args)
    {
        int wait = args.Length > 0 ? int.Parse(args[0]) : 30;
        log = new StreamWriter(@"C:\Users\Public\gate_keys.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        pid = (uint)ps[0].Id;
        EnumWindows(FindMain, IntPtr.Zero);
        if (main == IntPtr.Zero) { log.WriteLine("main window not found"); log.Close(); return 1; }

        // 1) открыть окно передачи ключей
        PostMessage(main, WM_COMMAND, (IntPtr)MENU_TRANSFER_KEYS, IntPtr.Zero);
        for (int i = 0; i < 20 && dlg == IntPtr.Zero; i++) { Thread.Sleep(500); EnumWindows(FindDlg, IntPtr.Zero); }
        if (dlg == IntPtr.Zero) { log.WriteLine("transfer window not opened"); log.Close(); return 1; }
        log.WriteLine("окно передачи открыто " + DateTime.Now.ToString("HH:mm:ss"));

        // 2) найти флажок и кнопки
        EnumChildWindows(dlg, FindCtl, IntPtr.Zero);
        log.WriteLine("chkAll=" + chkAll + " btnRun=" + btnRun + " btnExit=" + btnExit);
        if (chkAll == IntPtr.Zero || btnRun == IntPtr.Zero)
        {
            log.WriteLine("controls not found");
            log.Close();
            return 1;
        }

        // 3) выбрать все точки и запустить
        SendMessage(chkAll, BM_SETCHECK, (IntPtr)BST_CHECKED, IntPtr.Zero);
        SendMessage(chkAll, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
        Thread.Sleep(700);
        log.WriteLine("«Выбрать все» нажато " + DateTime.Now.ToString("HH:mm:ss"));

        SendMessage(btnRun, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
        log.WriteLine("«Выполнить» нажато " + DateTime.Now.ToString("HH:mm:ss"));

        // 4) ждать окончания: пока идёт рассылка, кнопка «Выполнить» недоступна
        int waited = 0;
        while (waited < wait)
        {
            Thread.Sleep(1000);
            waited++;
            if (!IsWindow(dlg)) { log.WriteLine("окно закрылось само через " + waited + " с"); break; }
            if (IsWindowEnabled(btnRun)) break;          // кнопка снова активна — готово
            if (waited % 10 == 0) log.WriteLine("  идёт рассылка, " + waited + " с");
        }
        log.WriteLine("ожидание окончено через " + waited + " с, кнопка активна: "
                      + (btnRun != IntPtr.Zero && IsWindowEnabled(btnRun)));

        // 5) закрыть окно, если оно ещё есть
        if (IsWindow(dlg) && btnExit != IntPtr.Zero)
        {
            SendMessage(btnExit, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
            log.WriteLine("«Выход» нажато " + DateTime.Now.ToString("HH:mm:ss"));
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
