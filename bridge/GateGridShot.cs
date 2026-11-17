using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateGridShot
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero, access = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        if (T(h).Contains("Управление точками доступа")) { access = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        if (C(h).Contains("MSFlexGrid")) grid = h;
        return true;
    }

    static int Main(string[] args)
    {
        int clickY = args.Length > 0 ? int.Parse(args[0]) : 28;
        log = new StreamWriter(@"C:\Users\Public\gate_gridshot.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero || access == IntPtr.Zero) { log.WriteLine("grid=" + grid + " access=" + access); log.Close(); return 2; }
        RECT gr; GetWindowRect(grid, out gr);
        log.WriteLine("grid rect=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom + " size=" + (gr.Right - gr.Left) + "x" + (gr.Bottom - gr.Top));

        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);

        SetCursorPos(gr.Left + 60, gr.Top + clickY);
        System.Threading.Thread.Sleep(150);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(600);
        log.WriteLine("clicked at y=" + clickY);

        int w = gr.Right - gr.Left, h = gr.Bottom - gr.Top;
        using (var bmp = new Bitmap(w, h))
        using (var g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(gr.Left, gr.Top, 0, 0, new Size(w, h));
            bmp.Save(@"C:\Users\Public\grid.png", ImageFormat.Png);
            int prev = -1;
            for (int y = 0; y < h; y++)
            {
                long r = 0, gg = 0, b = 0;
                for (int x = 5; x < w - 20; x += 4)
                {
                    Color c = bmp.GetPixel(x, y);
                    r += c.R; gg += c.G; b += c.B;
                }
                int n = (w - 25) / 4;
                int ar = (int)(r / n), ag = (int)(gg / n), ab = (int)(b / n);
                int key = (ar << 16) | (ag << 8) | ab;
                if (prev == -1 || Math.Abs(ar - ((prev >> 16) & 0xFF)) + Math.Abs(ag - ((prev >> 8) & 0xFF)) + Math.Abs(ab - (prev & 0xFF)) > 12)
                {
                    log.WriteLine("y=" + y + " rgb=" + ar + "," + ag + "," + ab);
                    prev = key;
                }
            }
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
