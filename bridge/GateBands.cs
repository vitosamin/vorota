using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateBands
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

    static void Click(int x, int y)
    {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(120);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero); System.Threading.Thread.Sleep(300);
    }

    static Bitmap Grab(RECT gr)
    {
        int w = gr.Right - gr.Left, h = gr.Bottom - gr.Top;
        var bmp = new Bitmap(w, h);
        using (var g = Graphics.FromImage(bmp)) g.CopyFromScreen(gr.Left, gr.Top, 0, 0, new Size(w, h));
        return bmp;
    }

    static int[] RowProfile(Bitmap bmp)
    {
        int w = bmp.Width, h = bmp.Height;
        int[] prof = new int[h];
        for (int y = 0; y < h; y++)
        {
            long r = 0, gg = 0, b = 0; int n = 0;
            for (int x = 5; x < w - 25; x += 3) { Color c = bmp.GetPixel(x, y); r += c.R; gg += c.G; b += c.B; n++; }
            prof[y] = (int)(b / n);
        }
        return prof;
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_bands.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero || access == IntPtr.Zero) { log.WriteLine("grid=" + grid + " access=" + access); log.Close(); return 2; }
        RECT gr; GetWindowRect(grid, out gr);
        log.WriteLine("grid rect=" + gr.Left + "," + gr.Top + "," + gr.Right + "," + gr.Bottom);

        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        SetForegroundWindow(access);
        AttachThreadInput(myT, fgT, false);
        System.Threading.Thread.Sleep(400);

        using (var b0 = Grab(gr))
        {
            int[] prof = RowProfile(b0);
            var sb = new StringBuilder();
            for (int y = 0; y < prof.Length; y++)
            {
                char ch = prof[y] < 60 ? '#' : (prof[y] < 150 ? '+' : (prof[y] < 235 ? '.' : ' '));
                sb.Append(ch);
            }
            log.WriteLine("profile: " + sb.ToString());
            log.WriteLine("dark lines at:");
            var darks = new List<int>();
            for (int y = 0; y < prof.Length; y++) if (prof[y] < 60) darks.Add(y);
            log.WriteLine(string.Join(",", darks.ConvertAll(x => x.ToString()).ToArray()));
        }

        int[] tests = { 27, 42, 57, 72, 87, 102, 117, 132, 147, 162 };
        foreach (int ty in tests)
        {
            Click(gr.Left + 60, gr.Top + ty);
            using (var b = Grab(gr))
            {
                int w = b.Width;
                var blueRows = new List<int>();
                for (int y = 0; y < b.Height; y++)
                {
                    long r = 0, gg = 0, bb = 0; int n = 0;
                    for (int x = 5; x < w - 25; x += 3) { Color c = b.GetPixel(x, y); r += c.R; gg += c.G; bb += c.B; n++; }
                    if (bb / n > r / n + 40) blueRows.Add(y);
                }
                if (blueRows.Count == 0) log.WriteLine("y=" + ty + " -> no blue");
                else log.WriteLine("y=" + ty + " -> blue " + blueRows[0] + ".." + blueRows[blueRows.Count - 1]);
            }
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
