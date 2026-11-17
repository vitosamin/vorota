using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

class GateBridge
{
    const string TOKEN = "vorota-2026";
    const int PORT = 8099;
    static readonly object uiLock = new object();
    static readonly string LogPath = @"C:\Users\Public\gate_bridge.log";

    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);

    static uint targetPid;
    static IntPtr mainWnd, accessWnd, grid, openBtn, lockBtn, unlockBtn;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

    static readonly string[,] Doors = {
        {"1","Сан пропускник - Вход"},
        {"2","Сан пропускник - Выход"},
        {"3","нет (офлайн)"},
        {"4","КПП2"},
        {"5","КПП1 - Выход"},
        {"6","КПП1 - Вход"},
        {"7","Кадры"},
        {"8","Кпп произ-во Вход"},
        {"9","Кпп произ-во Выход"},
        {"10","Досмотровая ВХОД"},
        {"11","Досмотровая ВЫХОД"},
        {"12","Вход из Зала"},
        {"13","Вход из ОППОМ"}
    };

    static void Log(string s)
    {
        try { File.AppendAllText(LogPath, DateTime.Now.ToString("s") + " " + s + Environment.NewLine, Encoding.UTF8); } catch { }
    }

    static bool Top(IntPtr h, IntPtr l)
    {
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (pid != targetPid) return true;
        string t = T(h);
        if (t.Contains("GATE Terminal")) mainWnd = h;
        if (t.Contains("Управление точками доступа")) accessWnd = h;
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton"))
        {
            if (t.Contains("Открыть дверь")) openBtn = h;
            else if (t.Contains("Заблокировать")) lockBtn = h;
            else if (t.Contains("Разблокировать")) unlockBtn = h;
        }
        return true;
    }

    static void Scan()
    {
        mainWnd = IntPtr.Zero; accessWnd = IntPtr.Zero; grid = IntPtr.Zero;
        openBtn = IntPtr.Zero; lockBtn = IntPtr.Zero; unlockBtn = IntPtr.Zero;
        EnumWindows(Top, IntPtr.Zero);
        if (accessWnd != IntPtr.Zero) EnumChildWindows(accessWnd, Child, IntPtr.Zero);
    }

    static bool WaitFor(Process p, int ms)
    {
        try { return p.WaitForExit(ms); } catch { return true; }
    }

    static void RefreshPid()
    {
        var ps = Process.GetProcessesByName("GateTerm");
        targetPid = ps.Length > 0 ? (uint)ps[0].Id : 0;
    }

    static bool EnsureReady()
    {
        RefreshPid();
        Scan();
        if (targetPid == 0)
        {
            try
            {
                Log("starting GateTerm");
                Process.Start(@"C:\GATE\Terminal\GateTerm.exe");
                Thread.Sleep(6000);
            }
            catch (Exception e) { Log("start err " + e.Message); }
            RefreshPid();
            Scan();
        }
        if (targetPid != 0 && mainWnd == IntPtr.Zero)
        {
            try
            {
                Log("running GateCtl login");
                var login = new ProcessStartInfo(@"C:\Users\Public\GateCtl.exe");
                login.UseShellExecute = false;
                login.CreateNoWindow = true;
                var lp = Process.Start(login);
                WaitFor(lp, 15000);
                Thread.Sleep(1500);
            }
            catch (Exception e) { Log("login err " + e.Message); }
            Scan();
        }
        if (mainWnd != IntPtr.Zero && accessWnd == IntPtr.Zero)
        {
            PostMessage(mainWnd, 0x0111, (IntPtr)83, IntPtr.Zero);
            Thread.Sleep(2200);
            Scan();
        }
        return mainWnd != IntPtr.Zero && accessWnd != IntPtr.Zero && grid != IntPtr.Zero;
    }

    static void ClickRow(int id)
    {
        int y = 24 + (id - 1) * 15;
        int x = 50;
        IntPtr lp = (IntPtr)((y << 16) | (x & 0xFFFF));
        PostMessage(grid, 0x0201, (IntPtr)1, lp);
        Thread.Sleep(150);
        PostMessage(grid, 0x0202, IntPtr.Zero, lp);
        Thread.Sleep(350);
    }

    static string Act(string action, int id)
    {
        lock (uiLock)
        {
            try
            {
                if (!EnsureReady()) return "{\"ok\":false,\"error\":\"gate ui not ready\"}";
                if (id < 1 || id >= Doors.GetLength(0) + 1) return "{\"ok\":false,\"error\":\"bad id\"}";
                ClickRow(id);
                IntPtr btn = action == "open" ? openBtn : (action == "lock" ? lockBtn : unlockBtn);
                if (btn == IntPtr.Zero) { Scan(); btn = action == "open" ? openBtn : (action == "lock" ? lockBtn : unlockBtn); }
                if (btn == IntPtr.Zero) return "{\"ok\":false,\"error\":\"button not found\"}";
                SendMessage(btn, 0x00F5, IntPtr.Zero, IntPtr.Zero);
                Thread.Sleep(500);
                Log(action + " id=" + id);
                return "{\"ok\":true,\"action\":\"" + action + "\",\"id\":" + id + "}";
            }
            catch (Exception e)
            {
                Log("act err " + e.Message);
                return "{\"ok\":false,\"error\":\"" + e.Message.Replace("\"", "'") + "\"}";
            }
        }
    }

    static string DoorsJson()
    {
        var sb = new StringBuilder();
        sb.Append("{\"doors\":[");
        for (int i = 0; i < Doors.GetLength(0); i++)
        {
            if (i > 0) sb.Append(",");
            sb.Append("{\"id\":").Append(Doors[i, 0]).Append(",\"name\":\"").Append(Doors[i, 1]).Append("\"}");
        }
        sb.Append("]}");
        return sb.ToString();
    }

    static void Respond(HttpListenerContext ctx, int code, string body)
    {
        try
        {
            byte[] data = Encoding.UTF8.GetBytes(body);
            ctx.Response.StatusCode = code;
            ctx.Response.ContentType = "application/json; charset=utf-8";
            ctx.Response.ContentLength64 = data.Length;
            ctx.Response.OutputStream.Write(data, 0, data.Length);
            ctx.Response.OutputStream.Close();
        }
        catch { }
    }

    static void Handle(HttpListenerContext ctx)
    {
        try
        {
            var q = ctx.Request.QueryString;
            string path = ctx.Request.Url.AbsolutePath.TrimEnd('/');
            if (q["token"] != TOKEN) { Respond(ctx, 403, "{\"ok\":false,\"error\":\"token\"}"); return; }
            if (path == "/doors") { Respond(ctx, 200, DoorsJson()); return; }
            if (path == "/status") { Respond(ctx, 200, "{\"state\":\"CLOSED\"}"); return; }
            int id;
            if (!int.TryParse(q["id"] ?? "", out id)) { Respond(ctx, 400, "{\"ok\":false,\"error\":\"id\"}"); return; }
            if (path == "/open") { Respond(ctx, 200, Act("open", id)); return; }
            if (path == "/lock") { Respond(ctx, 200, Act("lock", id)); return; }
            if (path == "/unlock") { Respond(ctx, 200, Act("unlock", id)); return; }
            Respond(ctx, 404, "{\"ok\":false,\"error\":\"not found\"}");
        }
        catch (Exception e)
        {
            Log("handle err " + e.Message);
            Respond(ctx, 500, "{\"ok\":false,\"error\":\"internal\"}");
        }
    }

    static void Main()
    {
        Log("bridge start");
        var listener = new HttpListener();
        listener.Prefixes.Add("http://+:" + PORT + "/");
        try { listener.Start(); }
        catch (Exception e) { Log("listen err " + e.Message); return; }
        Log("listening " + PORT);
        while (true)
        {
            var ctx = listener.GetContext();
            ThreadPool.QueueUserWorkItem(_ => Handle(ctx));
        }
    }
}
