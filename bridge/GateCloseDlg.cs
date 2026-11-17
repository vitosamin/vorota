using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class GateCloseDlg
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
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;
    static StreamWriter log;
    static uint pid;
    static IntPtr dlg = IntPtr.Zero, exitBtn = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint p; GetWindowThreadProcessId(h, out p);
        if (p != pid) return true;
        string t = T(h);
        if (t.Contains("Настройка реакций")) dlg = h;
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string t = T(h);
        log.WriteLine("  ctl: " + C(h) + " [" + t + "]");
        if (C(h).Contains("CommandButton") && t.Trim() == "Выход") exitBtn = h;
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
        log = new StreamWriter(@"C:\Users\Public\gate_closedlg.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return; }
        pid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("dlg=" + dlg + " visible=" + (dlg != IntPtr.Zero && IsWindowVisible(dlg)));
        if (dlg == IntPtr.Zero) { log.WriteLine("no dialog"); log.Close(); return; }
        EnumChildWindows(dlg, Child, IntPtr.Zero);
        if (exitBtn != IntPtr.Zero)
        {
            RECT br; GetWindowRect(exitBtn, out br);
            log.WriteLine("click Выход at " + ((br.Left + br.Right) / 2) + "," + ((br.Top + br.Bottom) / 2));
            SetCursorPos((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
            Thread.Sleep(200);
            for (int i = 0; i < 2; i++)
            {
                SetCursorPos((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
                Thread.Sleep(150);
                mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
                Thread.Sleep(70);
                mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
                Thread.Sleep(500);
            }
            Thread.Sleep(1200);
        }
        else
        {
            log.WriteLine("no exit button, posting WM_CLOSE");
            PostMessage(dlg, 0x0010, IntPtr.Zero, IntPtr.Zero);
            Thread.Sleep(1500);
        }
        log.WriteLine("dlg still visible=" + IsWindowVisible(dlg));
        Shot(@"C:\Users\Public\shot_closed.png");
        log.WriteLine("done");
        log.Close();
    }
}
