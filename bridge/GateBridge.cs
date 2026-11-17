using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

/// <summary>
/// HTTP-мост Gate-IP (v3): открывает двери через окно GateTerm «Управление точками доступа».
/// Соответствие «строка таблицы → дверь/направление» берётся из gate_map.json, который
/// строит разовая калибровка (/calibrate): мост открывает каждую строку и читает журнал Gate.
/// </summary>
class GateBridge
{
    const string TOKEN = "vorota-2026";
    const int PORT = 8099;
    const int ROW_BASE = 42;      // центр строки данных 1: 42 + 16*1
    const int ROW_H = 16;
    const int ROWS_MAX = 20;
    const string MAP_PATH = @"C:\Users\Public\gate_map.json";
    const string EVENT_PATH = @"C:\Users\Public\last_event.txt";
    static readonly object uiLock = new object();
    static readonly string LogPath = @"C:\Users\Public\gate_bridge.log";

    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    struct RECT { public int Left, Top, Right, Bottom; }
    const uint MDOWN = 0x0002, MUP = 0x0004;

    class Entry
    {
        public int Row;
        public int Dev;
        public int Rdr;
        public string Name = "";
        public int Num;
    }

    // Считыватели из базы Gate (RdrPtr, DevPtr, Num, имя) — для подписей «Вход»/«Выход».
    static readonly object[][] Readers = {
        new object[] { 1, 1, 1, "Сан пропускник - Вход" },
        new object[] { 2, 1, 2, "Сан пропускник - Выход" },
        new object[] { 3, 2, 1, "Магазин - Вход" },
        new object[] { 4, 2, 2, "Магазин - Выход" },
        new object[] { 9, 5, 1, "КПП2 - Вход" },
        new object[] { 10, 5, 2, "КПП2 - Выход" },
        new object[] { 11, 6, 1, "КПП1 - Выход" },
        new object[] { 12, 6, 2, "КПП1 - Вход" },
        new object[] { 15, 8, 1, "Кадры вход" },
        new object[] { 16, 8, 2, "Кадры выход" },
        new object[] { 17, 9, 1, "КПП производство - Вход" },
        new object[] { 18, 9, 2, "КПП производство - Выход" },
        new object[] { 21, 11, 1, "Досмотровая - Выход" },
        new object[] { 22, 11, 2, "Досмотровая - Вход" },
        new object[] { 25, 13, 1, "Вход из Зала" },
        new object[] { 26, 13, 2, "Вход из СЛ.ПОМ" },
    };

    static readonly Dictionary<int, Entry> Map = new Dictionary<int, Entry>();  // row -> entry
    static uint targetPid;
    static IntPtr mainWnd, accessWnd, grid, openBtn;
    static bool freshForm = false;

    static string T(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
    static string C(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

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
        if (t.Contains("Управление точками доступа")) { accessWnd = h; EnumChildWindows(h, Child, IntPtr.Zero); }
        return true;
    }

    static bool Child(IntPtr h, IntPtr l)
    {
        string c = C(h), t = T(h);
        if (c.Contains("MSFlexGrid")) grid = h;
        if (c.Contains("CommandButton") && t.Contains("Открыть дверь")) openBtn = h;
        return true;
    }

    static void Scan()
    {
        mainWnd = IntPtr.Zero; accessWnd = IntPtr.Zero; grid = IntPtr.Zero; openBtn = IntPtr.Zero;
        EnumWindows(Top, IntPtr.Zero);
    }

    static void RefreshPid()
    {
        var ps = Process.GetProcessesByName("GateTerm");
        targetPid = ps.Length > 0 ? (uint)ps[0].Id : 0;
    }

    static void Focus()
    {
        IntPtr fg = GetForegroundWindow();
        uint fgT = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint myT = GetCurrentThreadId();
        AttachThreadInput(myT, fgT, true);
        ShowWindow(accessWnd, 5);
        SetForegroundWindow(accessWnd);
        AttachThreadInput(myT, fgT, false);
        Thread.Sleep(300);
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y);
        Thread.Sleep(110);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(60);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(230);
    }

    static void ResetForm()
    {
        if (accessWnd != IntPtr.Zero)
        {
            IntPtr exitBtn = IntPtr.Zero;
            EnumChildWindows(accessWnd, (h, l) =>
            {
                if (C(h).Contains("CommandButton") && T(h).Trim() == "Выход") exitBtn = h;
                return true;
            }, IntPtr.Zero);
            if (exitBtn != IntPtr.Zero)
            {
                Focus();
                RECT br; GetWindowRect(exitBtn, out br);
                Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
                Thread.Sleep(700);
            }
        }
        Scan();
        if (mainWnd != IntPtr.Zero)
        {
            PostMessage(mainWnd, 0x0111, (IntPtr)83, IntPtr.Zero);
            Thread.Sleep(2200);
        }
        Scan();
        freshForm = accessWnd != IntPtr.Zero && grid != IntPtr.Zero && openBtn != IntPtr.Zero;
    }

    static bool EnsureReady()
    {
        RefreshPid();
        Scan();
        if (targetPid == 0)
        {
            try
            {
                Log("GateTerm not running, starting");
                Process.Start(@"C:\GATE\Terminal\GateTerm.exe");
                Thread.Sleep(7000);
            }
            catch (Exception e) { Log("start err " + e.Message); }
            RefreshPid();
            Scan();
        }
        if (targetPid != 0 && mainWnd == IntPtr.Zero)
        {
            try
            {
                Log("logging in via GateCtl");
                var psi = new ProcessStartInfo(@"C:\Users\Public\GateCtl.exe");
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                var p = Process.Start(psi);
                p.WaitForExit(15000);
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
        bool ready = accessWnd != IntPtr.Zero && grid != IntPtr.Zero && openBtn != IntPtr.Zero;
        if (ready && !freshForm) ResetForm();
        return freshForm;
    }

    /// <summary>Проверка по подсветке, что выбрана ожидаемая строка.</summary>
    static bool VerifyRow(RECT gr, int row)
    {
        try
        {
            int y = gr.Top + ROW_BASE + row * ROW_H;
            using (var bmp = new Bitmap(4, 4))
            using (var g = Graphics.FromImage(bmp))
            {
                g.CopyFromScreen(gr.Left + 40, y - 2, 0, 0, new Size(4, 4));
                int r = 0, gg = 0, b = 0;
                for (int i = 0; i < 4; i++)
                    for (int j = 0; j < 4; j++)
                    {
                        Color c = bmp.GetPixel(i, j);
                        r += c.R; gg += c.G; b += c.B;
                    }
                return (b / 16) > (r / 16) + 40;
            }
        }
        catch { return false; }
    }

    static bool SelectRow(int row)
    {
        RECT gr; GetWindowRect(grid, out gr);
        for (int attempt = 0; attempt < 3; attempt++)
        {
            int y = gr.Top + ROW_BASE + row * ROW_H + (attempt == 0 ? 0 : (attempt == 1 ? 2 : -2));
            Click(gr.Left + 60, y);
            Thread.Sleep(220);
            if (VerifyRow(gr, row)) return true;
        }
        Log("select failed row=" + row);
        return false;
    }

    /// <summary>Закрывает модальные окна GateTerm (OK/Да), если они появились.</summary>
    static void DismissDialogs()
    {
        int guard = 0;
        while (guard++ < 5)
        {
            IntPtr dlg = IntPtr.Zero;
            EnumWindows((h, l) =>
            {
                uint pid; GetWindowThreadProcessId(h, out pid);
                if (pid != targetPid) return true;
                if (C(h) == "#32770") dlg = h;
                return true;
            }, IntPtr.Zero);
            if (dlg == IntPtr.Zero) return;
            Log("dismiss dialog");
            EnumChildWindows(dlg, (h, l) =>
            {
                string t = T(h);
                if (C(h) == "Button" && (t == "OK" || t == "ОК" || t == "Да" || t == "&OK"))
                {
                    RECT br; GetWindowRect(h, out br);
                    Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
                }
                return true;
            }, IntPtr.Zero);
            Thread.Sleep(500);
        }
    }

    static void ClickOpen()
    {
        RECT br; GetWindowRect(openBtn, out br);
        Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
    }

    /// <summary>Нажимает кнопку окна по подписи (Открыть дверь / Заблокировать / Разблокировать).</summary>
    static bool PressButton(string label)
    {
        IntPtr btn = IntPtr.Zero;
        EnumChildWindows(accessWnd, (h, l) =>
        {
            if (C(h).Contains("CommandButton") && T(h).Trim() == label) btn = h;
            return true;
        }, IntPtr.Zero);
        if (btn == IntPtr.Zero || !IsWindowEnabled(btn)) return false;
        RECT br; GetWindowRect(btn, out br);
        Click((br.Left + br.Right) / 2, (br.Top + br.Bottom) / 2);
        return true;
    }

    static string lastStamp = "";
    static int lastIndex = 0;

    /// <summary>Отметка времени последнего прочитанного события (для проверки новизны).</summary>
    static string LastStamp()
    {
        try
        {
            if (!File.Exists(EVENT_PATH)) return "0";
            string line = File.ReadAllText(EVENT_PATH, Encoding.Default).Trim();
            string[] parts = line.Split(';');
            return parts.Length > 0 ? parts[0] : "0";
        }
        catch { return "0"; }
    }

    static int NumOfReader(int rdr)
    {
        foreach (var r in Readers) if ((int)r[0] == rdr) return (int)r[2];
        return 0;
    }

    /// <summary>Читает последнее событие «команда открывания» из журнала Gate (через 32-битный cscript).</summary>
    static int[] LastEvent(string sinceStamp)
    {
        try
        {
            if (File.Exists(EVENT_PATH)) File.Delete(EVENT_PATH);
            var psi = new ProcessStartInfo(@"C:\Windows\SysWOW64\cscript.exe",
                "//nologo \"C:\\Users\\Public\\read_last_event.vbs\" \"" + EVENT_PATH + "\"");
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            var p = Process.Start(psi);
            p.WaitForExit(10000);
            if (!File.Exists(EVENT_PATH)) return null;
            string line = File.ReadAllText(EVENT_PATH, Encoding.Default).Trim();
            string[] parts = line.Split(';');
            if (parts.Length < 3) return null;
            int idx = int.Parse(parts[0].Trim());
            int sinceIdx = 0;
            int.TryParse(sinceStamp, out sinceIdx);
            if (idx <= sinceIdx) return null;
            lastIndex = idx;
            return new[] { int.Parse(parts[1].Trim()), int.Parse(parts[2].Trim()) };
        }
        catch (Exception e) { Log("lastevent err " + e.Message); return null; }
    }

    static void SaveMap()
    {
        var sb = new StringBuilder("{\"rows\":[");
        bool first = true;
        var rows = new List<int>(Map.Keys);
        rows.Sort();
        foreach (int r in rows)
        {
            var e = Map[r];
            if (!first) sb.Append(",");
            first = false;
            sb.Append("{\"row\":").Append(e.Row)
              .Append(",\"dev\":").Append(e.Dev)
              .Append(",\"rdr\":").Append(e.Rdr)
              .Append(",\"num\":").Append(e.Num)
              .Append(",\"name\":\"").Append(e.Name).Append("\"}");
        }
        sb.Append("]}");
        File.WriteAllText(MAP_PATH, sb.ToString(), Encoding.UTF8);
    }

    static void LoadMap()
    {
        Map.Clear();
        try
        {
            if (!File.Exists(MAP_PATH)) return;
            string body = File.ReadAllText(MAP_PATH, Encoding.UTF8);
            int i = body.IndexOf("\"rows\":[");
            if (i < 0) return;
            string arr = body.Substring(i + 8);
            int end = arr.LastIndexOf(']');
            if (end >= 0) arr = arr.Substring(0, end);
            foreach (string obj in arr.Split(new[] { "}," }, StringSplitOptions.RemoveEmptyEntries))
            {
                var e = new Entry();
                e.Row = IntOf(obj, "\"row\":");
                e.Dev = IntOf(obj, "\"dev\":");
                e.Rdr = IntOf(obj, "\"rdr\":");
                e.Num = IntOf(obj, "\"num\":");
                e.Name = StrOf(obj, "\"name\":\"");
                if (e.Row > 0) Map[e.Row] = e;
            }
            Log("map loaded rows=" + Map.Count);
        }
        catch (Exception ex) { Log("map load err " + ex.Message); }
    }

    static int IntOf(string s, string key)
    {
        int i = s.IndexOf(key);
        if (i < 0) return 0;
        i += key.Length;
        int j = i;
        while (j < s.Length && (char.IsDigit(s[j]) || s[j] == '-')) j++;
        int v;
        return int.TryParse(s.Substring(i, j - i), out v) ? v : 0;
    }

    static string StrOf(string s, string key)
    {
        int i = s.IndexOf(key);
        if (i < 0) return "";
        i += key.Length;
        int j = s.IndexOf('"', i);
        return j < 0 ? "" : s.Substring(i, j - i);
    }

    /// <summary>Калибровка: открывает каждую строку и по журналу определяет дверь.</summary>
    static string Calibrate(int fromRow)
    {
        lock (uiLock)
        {
            try
            {
                if (!EnsureReady()) return "{\"ok\":false,\"error\":\"gate ui not ready\"}";
                Focus();
                if (fromRow <= 1) Map.Clear();
                var report = new StringBuilder();
                for (int row = fromRow; row <= ROWS_MAX; row++)
                {
                    DismissDialogs();
                    if (!SelectRow(row))
                    {
                        report.Append("row ").Append(row).Append(": select failed; ");
                        break;
                    }
                    string stamp = LastStamp();
                    int[] ev = null;
                    for (int attempt = 0; attempt < 3 && ev == null; attempt++)
                    {
                        ClickOpen();
                        for (int w = 0; w < 8 && ev == null; w++)
                        {
                            Thread.Sleep(500);
                            ev = LastEvent(stamp);
                        }
                    }
                    if (ev == null)
                    {
                        report.Append("row ").Append(row).Append(": no new event; ");
                        Log("calibrate row=" + row + " no new event");
                        continue;
                    }
                    var e = new Entry { Row = row, Dev = ev[0], Rdr = ev[1], Num = NumOfReader(ev[1]) };
                    Map[row] = e;
                    report.Append("row ").Append(row).Append("=dev").Append(e.Dev).Append("/rdr").Append(e.Rdr).Append("; ");
                    Log("calibrate row=" + row + " dev=" + e.Dev + " rdr=" + e.Rdr);
                }
                SaveMap();
                return "{\"ok\":true,\"rows\":" + Map.Count + ",\"report\":\"" + report.ToString().Replace("\"", "'") + "\"}";
            }
            catch (Exception e)
            {
                Log("calibrate err " + e.Message);
                return "{\"ok\":false,\"error\":\"" + e.Message.Replace("\"", "'") + "\"}";
            }
        }
    }

    static string OpenRows(List<int> rows)
    {
        lock (uiLock)
        {
            try
            {
                if (Map.Count == 0) return "{\"ok\":false,\"error\":\"not calibrated\"}";
                if (!EnsureReady()) return "{\"ok\":false,\"error\":\"gate ui not ready\"}";
                Focus();
                var opened = new List<int>();
                var failed = new List<int>();
                foreach (int row in rows)
                {
                    if (!SelectRow(row)) { failed.Add(row); continue; }
                    ClickOpen();
                    Thread.Sleep(600);
                    opened.Add(row);
                    Log("open row=" + row);
                }
                return "{\"ok\":" + (failed.Count == 0 ? "true" : "false")
                    + ",\"opened\":[" + string.Join(",", opened.ConvertAll(x => x.ToString()).ToArray()) + "]"
                    + ",\"failed\":[" + string.Join(",", failed.ConvertAll(x => x.ToString()).ToArray()) + "]}";
            }
            catch (Exception e)
            {
                Log("open err " + e.Message);
                return "{\"ok\":false,\"error\":\"" + e.Message.Replace("\"", "'") + "\"}";
            }
        }
    }

    static string DoorsJson()
    {
        // rdr -> row (из калибровки), дедупликация по rdr
        var rowByRdr = new Dictionary<int, int>();
        foreach (var e in Map.Values)
        {
            if (!rowByRdr.ContainsKey(e.Rdr) || e.Row < rowByRdr[e.Rdr]) rowByRdr[e.Rdr] = e.Row;
        }
        var devices = new List<int>();
        var perDev = new Dictionary<int, List<object[]>>();
        foreach (var r in Readers)
        {
            int rdr = (int)r[0], dev = (int)r[1];
            if (!rowByRdr.ContainsKey(rdr)) continue;   // не откалибровано — не показываем
            if (!perDev.ContainsKey(dev)) { perDev[dev] = new List<object[]>(); devices.Add(dev); }
            perDev[dev].Add(r);
        }
        devices.Sort();
        var sb = new StringBuilder("{\"doors\":[");
        bool firstDoor = true;
        foreach (int dev in devices)
        {
            var list = perDev[dev];
            list.Sort((a, b) => ((int)a[2]).CompareTo((int)b[2]));
            if (!firstDoor) sb.Append(",");
            firstDoor = false;
            sb.Append("{\"id\":").Append(dev).Append(",\"name\":\"").Append(DeviceName(dev)).Append("\",\"readers\":[");
            for (int i = 0; i < list.Count; i++)
            {
                int rdr = (int)list[i][0], num = (int)list[i][2];
                string full = (string)list[i][3];
                if (i > 0) sb.Append(",");
                sb.Append("{\"row\":").Append(rowByRdr[rdr])
                  .Append(",\"rdr\":").Append(rdr)
                  .Append(",\"dir\":\"").Append(full.ToLower().Contains("выход") ? "out" : "in")
                  .Append("\",\"label\":\"").Append(full).Append("\"}");
            }
            sb.Append("]}");
        }
        sb.Append("]}");
        return sb.ToString();
    }

    static string DeviceName(int dev)
    {
        switch (dev)
        {
            case 1: return "Сан пропускник";
            case 2: return "Магазин (офлайн)";
            case 5: return "КПП2";
            case 6: return "КПП1";
            case 8: return "Кадры";
            case 9: return "КПП производство";
            case 11: return "Досмотровая";
            case 13: return "Вход из Зала";
            default: return "Дверь " + dev;
        }
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
            if (path == "/status") { Respond(ctx, 200, "{\"state\":\"CLOSED\",\"calibrated\":" + (Map.Count > 0 ? "true" : "false") + "}"); return; }
            if (path == "/doors") { Respond(ctx, 200, DoorsJson()); return; }
            if (path == "/calibrate")
            {
                int fromRow = 1;
                int.TryParse(q["from"] ?? "1", out fromRow);
                Respond(ctx, 200, Calibrate(fromRow));
                return;
            }
            if (path == "/reload") { LoadMap(); Respond(ctx, 200, "{\"ok\":true,\"rows\":" + Map.Count + "}"); return; }
            int id;
            if (!int.TryParse(q["id"] ?? "", out id)) { Respond(ctx, 400, "{\"ok\":false,\"error\":\"id\"}"); return; }
            if (path == "/press")
            {
                string btnName = q["btn"] ?? "";
                string label = btnName == "unlock" ? "Разблокировать" : (btnName == "lock" ? "Заблокировать" : "Открыть дверь");
                lock (uiLock)
                {
                    if (!EnsureReady()) { Respond(ctx, 500, "{\"ok\":false,\"error\":\"gate ui not ready\"}"); return; }
                    Focus();
                    if (id > 0 && !SelectRow(id)) { Respond(ctx, 500, "{\"ok\":false,\"error\":\"select failed\"}"); return; }
                    bool ok = PressButton(label);
                    Respond(ctx, 200, "{\"ok\":" + (ok ? "true" : "false") + ",\"button\":\"" + label + "\"}");
                }
                return;
            }
            if (path == "/open")
            {
                if (Map.Count == 0) { Respond(ctx, 409, "{\"ok\":false,\"error\":\"not calibrated\"}"); return; }
                string dir = q["dir"] ?? "";
                var rows = new List<int>();
                var seen = new HashSet<int>();
                foreach (var e in Map.Values)
                {
                    if (e.Dev != id) continue;
                    if (!seen.Add(e.Rdr)) continue;          // дедуп по считывателю
                    int num = NumOfReader(e.Rdr);
                    if (dir == "in" && num == 2) continue;
                    if (dir == "out" && num != 2) continue;
                    rows.Add(e.Row);
                }
                if (rows.Count == 0) { Respond(ctx, 404, "{\"ok\":false,\"error\":\"door\"}"); return; }
                rows.Sort();
                Respond(ctx, 200, OpenRows(rows));
                return;
            }
            if (path == "/openrow")
            {
                if (Map.Count == 0) { Respond(ctx, 409, "{\"ok\":false,\"error\":\"not calibrated\"}"); return; }
                Respond(ctx, 200, OpenRows(new List<int> { id }));
                return;
            }
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
        LoadMap();
        Log("bridge 3.0 start, mapped rows=" + Map.Count);
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
