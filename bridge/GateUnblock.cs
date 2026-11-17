using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

/// <summary>Находит строку, у которой доступна кнопка «Разблокировать», и снимает блокировку.</summary>
class GateUnblock
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero, access = IntPtr.Zero, unlockBtn = IntPtr.Zero, mainWnd = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("GATE Terminal")) mainWnd = h;
        if (t.Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Trim() == "Разблокировать") unlockBtn = h;
        return true;
    }

    static void Scan() { mainWnd = IntPtr.Zero; access = IntPtr.Zero; grid = IntPtr.Zero; unlockBtn = IntPtr.Zero; EnumWindows(Top, IntPtr.Zero); }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(110);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(250);
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_unblock.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        Scan();
        if (access == IntPtr.Zero && mainWnd != IntPtr.Zero)
        {
            PostMessage(mainWnd, 0x0111, (IntPtr)83, IntPtr.Zero);
            System.Threading.Thread.Sleep(2500);
            Scan();
        }
        if (access == IntPtr.Zero || grid == IntPtr.Zero) { log.WriteLine("access=" + access + " grid=" + grid); log.Close(); return 2; }
        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        ShowWindow(access, 5);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);
        RECT gr; GetWindowRect(grid, out gr);
        log.WriteLine("grid=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom);
        for (int row = 1; row <= 16; row++)
        {
            int y = gr.Top + 42 + 16 * row;
            if (y > gr.Bottom - 4) break;
            Click(gr.Left + 60, y);
            System.Threading.Thread.Sleep(300);
            bool en = unlockBtn != IntPtr.Zero && IsWindowEnabled(unlockBtn);
            log.WriteLine("row=" + row + " unlock_enabled=" + en);
            if (en)
            {
                RECT br; GetWindowRect(unlockBtn, out br);
                log.WriteLine("unblocking row=" + row + " at " + DateTime.Now.ToString("HH:mm:ss.fff"));
                Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
                System.Threading.Thread.Sleep(1200);
                log.WriteLine("after click unlock_enabled=" + IsWindowEnabled(unlockBtn));
                break;
            }
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
