using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateAcc
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint idObject, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out object ppvObject);
    [DllImport("oleacc.dll")] static extern int AccessibleChildren(object paccContainer, int iChildStart, int cChildren, [Out] object[] rgvarChildren, out int pcObtained);

    static readonly Guid IID_IAccessible = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71");
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

    static void Walk(object acc, int depth, int max)
    {
        if (acc == null || depth > max) return;
        dynamic a = acc;
        string name = "", value = "", role = "";
        try { name = a.get_accName(0); } catch { }
        try { value = a.get_accValue(0); } catch { }
        try { role = a.get_accRole(0).ToString(); } catch { }
        log.WriteLine(new string(' ', depth * 2) + "role=" + role + " name=[" + name + "] value=[" + value + "]");
        int cnt = 0;
        try { cnt = a.accChildCount; } catch { return; }
        if (cnt <= 0) return;
        object[] kids = new object[cnt];
        int got;
        if (AccessibleChildren(acc, 0, cnt, kids, out got) != 0) return;
        for (int i = 0; i < got; i++) Walk(kids[i], depth + 1, max);
    }

    static void Try(IntPtr hwnd, uint objid, string label, int max)
    {
        object acc = null;
        Guid iid = IID_IAccessible;
        int hr = AccessibleObjectFromWindow(hwnd, objid, ref iid, out acc);
        log.WriteLine("=== " + label + " hwnd=" + hwnd + " objid=" + objid + " hr=" + hr + " acc=" + (acc == null ? "null" : "ok"));
        if (acc != null) { try { Walk(acc, 0, max); } catch (Exception e) { log.WriteLine("walk err " + e.Message); } }
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_acc.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        log.WriteLine("access=" + access + " grid=" + grid);
        if (access != IntPtr.Zero)
        {
            Try(access, 0xFFFFFFFC, "form OBJID_CLIENT", 2);
            Try(access, 0, "form OBJID_WINDOW", 2);
        }
        if (grid != IntPtr.Zero)
        {
            Try(grid, 0xFFFFFFFC, "grid OBJID_CLIENT", 3);
            Try(grid, 0, "grid OBJID_WINDOW", 3);
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
