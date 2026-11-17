using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class GateShotSeq
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
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
        if (T(h).Contains("Управление точками")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
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

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); Thread.Sleep(70);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); Thread.Sleep(50);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); Thread.Sleep(150);
    }

    static void Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_seq.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        pid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (access == IntPtr.Zero || grid == IntPtr.Zero || openBtn == IntPtr.Zero) { log.WriteLine("missing"); log.Close(); return; }
        RECT gr; GetWindowRect(grid, out gr);
        RECT br; GetWindowRect(openBtn, out br);
        log.WriteLine("grid=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom);
        log.WriteLine("btn=" + br.Left + "," + br.Top + "," + br.Right + "," + br.Bottom);
        // активируем окно кликом по заголовку
        Click(gr.Left - 40, gr.Top - 8);
        Thread.Sleep(300);
        log.WriteLine("foreground title=[" + T(GetForegroundWindow()) + "]");
        // строка 9 (Кпп произ-во выход): по снимку y = gridTop + 18 + 16*n
        int y = gr.Top + 18 + 16 * 9;
        log.WriteLine("select row 9 at y=" + y);
        Click(gr.Left + 120, y);
        Thread.Sleep(300);
        Shot(@"C:\Users\Public\seq_select.png");
        int cx = (br.Left + br.Right) / 2, cy = (br.Top + br.Bottom) / 2;
        log.WriteLine("click open at " + cx + "," + cy);
        Click(cx, cy);
        Thread.Sleep(400);
        Shot(@"C:\Users\Public\seq_after1.png");
        Thread.Sleep(2500);
        Shot(@"C:\Users\Public\seq_after2.png");
        log.WriteLine("foreground now=[" + T(GetForegroundWindow()) + "]");
        log.WriteLine("done");
        log.Close();
    }
}
