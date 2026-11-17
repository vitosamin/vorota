using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateCtl
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, string l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);

    struct RECT { public int Left, Top, Right, Bottom; }

    static StreamWriter log;
    static uint targetPid;
    static IntPtr dialog = IntPtr.Zero;
    static List<IntPtr> boxes = new List<IntPtr>();
    static List<KeyValuePair<IntPtr, string>> buttons = new List<KeyValuePair<IntPtr, string>>();

    static string Text(IntPtr h)
    {
        var sb = new StringBuilder(1024);
        GetWindowText(h, sb, 1024);
        return sb.ToString();
    }

    static string Cls(IntPtr h)
    {
        var sb = new StringBuilder(256);
        GetClassName(h, sb, 256);
        return sb.ToString();
    }

    static bool TopCb(IntPtr h, IntPtr l)
    {
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        RECT r;
        GetWindowRect(h, out r);
        string t = Text(h), c = Cls(h);
        log.WriteLine("top h=" + h + " class=" + c + " text=" + t + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);
        if (t.Contains("Регистрация")) dialog = h;
        if ((r.Right - r.Left) > 50 && (r.Bottom - r.Top) > 50 && !t.Contains("Регистрация"))
        {
            try { SaveWindow(h, @"C:\Users\Public\gatectl_" + h.ToString() + ".png"); }
            catch (Exception e) { log.WriteLine("save err " + e.Message); }
        }
        return true;
    }

    static bool ChildCb(IntPtr h, IntPtr l)
    {
        string c = Cls(h), t = Text(h);
        if (c.Contains("TextBox")) boxes.Add(h);
        if (c.Contains("CommandButton")) buttons.Add(new KeyValuePair<IntPtr, string>(h, t));
        log.WriteLine("  child h=" + h + " class=" + c + " text=" + t);
        return true;
    }

    static void SaveWindow(IntPtr h, string path)
    {
        RECT r;
        if (!GetWindowRect(h, out r)) return;
        int w = r.Right - r.Left, ht = r.Bottom - r.Top;
        if (w <= 0 || ht <= 0) return;
        using (var bmp = new Bitmap(w, ht))
        using (var g = Graphics.FromImage(bmp))
        {
            IntPtr hdc = g.GetHdc();
            bool ok = PrintWindow(h, hdc, 2);
            g.ReleaseHdc(hdc);
            bmp.Save(path, ImageFormat.Png);
            log.WriteLine("saved " + path + " " + w + "x" + ht + " ok=" + ok);
        }
    }

    static int Main(string[] args)
    {
        log = new StreamWriter(@"C:\Users\Public\gatectl.txt", false, Encoding.UTF8);
        log.WriteLine("start " + DateTime.Now + " session=" + Process.GetCurrentProcess().SessionId);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        log.WriteLine("pid=" + targetPid);
        EnumWindows(TopCb, IntPtr.Zero);
        if (dialog == IntPtr.Zero) { log.WriteLine("no login dialog"); log.Close(); return 2; }
        EnumChildWindows(dialog, ChildCb, IntPtr.Zero);
        log.WriteLine("boxes=" + boxes.Count + " buttons=" + buttons.Count);
        if (boxes.Count >= 2)
        {
            SendMessage(boxes[0], 0x000C, IntPtr.Zero, "Admin");
            SendMessage(boxes[1], 0x000C, IntPtr.Zero, "admin1720");
            log.WriteLine("filled");
        }
        foreach (var b in buttons)
        {
            if (b.Value == "OK")
            {
                SendMessage(b.Key, 0x00F5, IntPtr.Zero, IntPtr.Zero);
                log.WriteLine("clicked OK");
            }
        }
        System.Threading.Thread.Sleep(4000);
        log.WriteLine("--- after ---");
        EnumWindows(TopCb, IntPtr.Zero);
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
