using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class GateDiag
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    struct POINT { public int X, Y; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint pid;
    static IntPtr access = IntPtr.Zero, grid = IntPtr.Zero, openBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        if (T(h).Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Contains("Открыть")) openBtn = h;
        return true;
    }

    static void Shot(string path)
    {
        Rectangle b = Screen.PrimaryScreen.Bounds;
        using (Bitmap bmp = new Bitmap(b.Width, b.Height, PixelFormat.Format32bppArgb))
        {
            using (Graphics g = Graphics.FromImage(bmp)) g.CopyFromScreen(b.X, b.Y, 0, 0, b.Size);
            bmp.Save(path, ImageFormat.Png);
        }
    }

    static void Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_diag.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return; }
        pid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " grid=" + grid + " openBtn=" + openBtn);
        if (openBtn == IntPtr.Zero) { log.WriteLine("no open button"); log.Close(); return; }
        RECT br; GetWindowRect(openBtn, out br);
        int cx = (br.Left + br.Right) / 2, cy = (br.Top + br.Bottom) / 2;
        log.WriteLine("openBtn rect=" + br.Left + "," + br.Top + "," + br.Right + "," + br.Bottom + " center=" + cx + "," + cy);
        log.WriteLine("openBtn enabled=" + IsWindowEnabled(openBtn) + " class=" + C(openBtn));
        IntPtr fg = GetForegroundWindow();
        log.WriteLine("foreground=" + fg + " title=" + T(fg));
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        AttachThreadInput(GetCurrentThreadId(), fgT, true);
        ShowWindow(access, 5);
        SetForegroundWindow(access);
        AttachThreadInput(GetCurrentThreadId(), fgT, false);
        Thread.Sleep(400);
        SetCursorPos(cx, cy);
        Thread.Sleep(200);
        POINT p; p.X = cx; p.Y = cy;
        IntPtr under = WindowFromPoint(p);
        log.WriteLine("window under cursor=" + under + " class=" + C(under) + " title=[" + T(under) + "]");
        Shot(@"C:\Users\Public\shot_before.png");
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(80);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(1500);
        Shot(@"C:\Users\Public\shot_after.png");
        IntPtr fg2 = GetForegroundWindow();
        log.WriteLine("after click foreground=" + fg2 + " title=" + T(fg2));
        log.WriteLine("done");
        log.Close();
    }
}
