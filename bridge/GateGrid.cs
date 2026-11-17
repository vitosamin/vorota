using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

class GateGrid
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
    const uint OBJID_CLIENT = 0xFFFFFFFC;

    static StreamWriter log;
    static uint targetPid;
    static IntPtr grid = IntPtr.Zero;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        if (T(h).Contains("Управление точками доступа")) EnumChildWindows(h, Child, IntPtr.Zero);
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        if (C(h).Contains("MSFlexGrid")) grid = h;
        return true;
    }

    static void Walk(object acc, int depth, int maxDepth)
    {
        if (acc == null || depth > maxDepth) return;
        dynamic a = acc;
        string name = "", value = "", role = "";
        try { name = a.get_accName(0); } catch { }
        try { value = a.get_accValue(0); } catch { }
        try { role = a.get_accRole(0).ToString(); } catch { }
        log.WriteLine(new string(' ', depth * 2) + "role=" + role + " name=[" + name + "] value=[" + value + "]");
        int count = 0;
        try { count = a.accChildCount; } catch { return; }
        if (count <= 0) return;
        object[] kids = new object[count];
        int obtained;
        int hr = AccessibleChildren(acc, 0, count, kids, out obtained);
        if (hr != 0) { log.WriteLine("AccessibleChildren hr=" + hr); return; }
        for (int i = 0; i < obtained; i++) Walk(kids[i], depth + 1, maxDepth);
    }

    static int Main()
    {
        log = new StreamWriter(@"C:\Users\Public\gate_grid.txt", false, Encoding.UTF8);
        log.AutoFlush = true;
        log.WriteLine("start " + DateTime.Now);
        Process[] ps = Process.GetProcessesByName("GateTerm");
        if (ps.Length == 0) { log.WriteLine("no GateTerm"); log.Close(); return 1; }
        targetPid = (uint)ps[0].Id;
        EnumWindows(Top, IntPtr.Zero);
        if (grid == IntPtr.Zero) { log.WriteLine("no grid"); log.Close(); return 2; }
        log.WriteLine("grid hwnd=" + grid);
        object acc = null;
        Guid iid = IID_IAccessible;
        int hr2 = AccessibleObjectFromWindow(grid, OBJID_CLIENT, ref iid, out acc);
        log.WriteLine("AccessibleObjectFromWindow hr=" + hr2 + " acc=" + (acc == null ? "null" : acc.GetType().FullName));
        if (acc != null)
        {
            try { Walk(acc, 0, 3); } catch (Exception e) { log.WriteLine("walk err " + e.Message); }
        }
        log.WriteLine("done");
        log.Close();
        return 0;
    }
}
