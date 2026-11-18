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
    // Ключ доступа больше не зашит в exe: до 3.15 он лежал прямо в коде и в
    // открытых релизах APK. Теперь exe читает его из файла на шаре C:\GATE
    // на каждый запрос — смена ключа не требует пересборки и перезапуска.
    const string TOKEN_FILE = @"C:\GATE\gate_token.txt";
    const string TOKEN_FILE_FALLBACK = @"C:\Users\Public\gate_token.txt";
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
    static bool sortChecked = false;

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
        Thread.Sleep(80);
    }

    static void Click(int x, int y)
    {
        SetCursorPos(x, y);
        Thread.Sleep(15);
        mouse_event(MDOWN, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(15);
        mouse_event(MUP, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(45);
    }

    /// <summary>Принудительно сортирует таблицу по первому столбцу (два клика = убывание),
    /// чтобы порядок строк всегда совпадал с калибровкой.</summary>
    static void ForceSort()
    {
        if (grid == IntPtr.Zero) return;
        RECT gr; GetWindowRect(grid, out gr);
        for (int i = 0; i < 2; i++)
        {
            Click(gr.Left + 60, gr.Top + 9);
            Thread.Sleep(250);
        }
        Log("force sort applied");
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
            using (var bmp = new Bitmap(2, 2))
            using (var g = Graphics.FromImage(bmp))
            {
                g.CopyFromScreen(gr.Left + 40, y - 1, 0, 0, new Size(2, 2));
                int r = 0, gg = 0, b = 0;
                for (int i = 0; i < 2; i++)
                    for (int j = 0; j < 2; j++)
                    {
                        Color c = bmp.GetPixel(i, j);
                        r += c.R; gg += c.G; b += c.B;
                    }
                return (b / 4) > (r / 4) + 40;
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
            Thread.Sleep(60);
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
        int cx = (br.Left + br.Right) / 2, cy = (br.Top + br.Bottom) / 2;
        bool active = GetForegroundWindow() == accessWnd;
        Click(cx, cy);
        if (!active) { Thread.Sleep(70); Click(cx, cy); }
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
        int cx = (br.Left + br.Right) / 2, cy = (br.Top + br.Bottom) / 2;
        Click(cx, cy);
        Thread.Sleep(180);
        Click(cx, cy);
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

    /// <summary>true, если считыватель — «выход» (по названию из базы Gate).</summary>
    static bool IsOut(int rdr)
    {
        foreach (var r in Readers)
            if ((int)r[0] == rdr) return ((string)r[3]).ToLower().Contains("выход");
        return false;
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
                ForceSort();
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
                    int[] ev = null;
                    for (int attempt = 0; attempt < 3 && ev == null; attempt++)
                    {
                        if (attempt > 0)
                        {
                            // перевыбор строки: клик по соседней, затем по нужной
                            int other = row == 1 ? 2 : 1;
                            SelectRow(other);
                            SelectRow(row);
                        }
                        string stamp = LastStamp();
                        int sinceIdx = 0;
                        int.TryParse(stamp, out sinceIdx);
                        ClickOpen();
                        for (int w = 0; w < 30 && ev == null; w++)
                        {
                            Thread.Sleep(500);
                            ev = LastEvent(sinceIdx.ToString());
                        }
                        // если открылась та же дверь, что и на прошлой строке — выбор не сработал
                        if (ev != null && Map.ContainsKey(row - 1) && Map[row - 1].Rdr == ev[1])
                        {
                            Log("calibrate row=" + row + " duplicate rdr=" + ev[1] + ", retry");
                            ev = null;
                        }
                    }
                    if (ev == null)
                    {
                        report.Append("row ").Append(row).Append(": no event; ");
                        Log("calibrate row=" + row + " no event");
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
                if (!sortChecked) { ForceSort(); sortChecked = true; }
                var opened = new List<int>();
                var swTotal = System.Diagnostics.Stopwatch.StartNew();
                var failed = new List<int>();
                foreach (int row in rows)
                {
                    if (!SelectRow(row)) { failed.Add(row); continue; }
                    ClickOpen();
                    opened.Add(row);
                    Log("open row=" + row);
                }
                Log("open took " + swTotal.ElapsedMilliseconds + " ms");
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


    const string WEB_USER = "vitosamin";
    const string WEB_PASS = "Admin910327";

    const string LoginPage = @"<!doctype html>
<html lang=""ru""><head><meta charset=""utf-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Вход · Ворота</title>
<style>
:root{--bg:#e3e6ea;--card:#eef0f3;--line:#d6dae0;--acc:#3f8471;--txt:#2a3037;--mut:#565f6b;--muted:#828a95}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.box{width:100%;max-width:380px}
.logo{width:60px;height:60px;border-radius:18px;background:#e4ede9;display:flex;align-items:center;justify-content:center;margin:0 auto 18px}
h1{font-size:26px;font-weight:600;text-align:center;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:13px;text-align:center;margin-bottom:26px}
form{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px rgba(16,24,40,.04)}
label{display:block;font-size:12px;color:var(--mut);margin:0 0 6px 2px;font-weight:500}
input{width:100%;background:#e7eaee;border:1px solid var(--line);color:var(--txt);border-radius:11px;padding:12px 14px;font-size:15px;margin-bottom:14px;outline:none;transition:.15s}
input:focus{border-color:var(--acc);background:#fff;box-shadow:0 0 0 3px rgba(63,132,113,.14)}
button{width:100%;border:0;border-radius:11px;padding:13px;font-size:15px;font-weight:600;color:#fff;background:var(--acc);cursor:pointer;transition:.15s}
button:hover{background:#356f5f}
button:active{transform:translateY(1px)}
.err{background:#fbeae8;border:1px solid #f0c9c4;color:#b3372d;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:14px}
.foot{color:var(--muted);font-size:11px;text-align:center;margin-top:18px}
</style></head><body>
<div class=""box"">
  <div class=""logo"">
    <svg width=""28"" height=""28"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#2f6b5b"" stroke-width=""1.8"" stroke-linecap=""round"" stroke-linejoin=""round"">
      <path d=""M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16""/><path d=""M15 12h5""/><path d=""M2 21h20""/><circle cx=""11"" cy=""12"" r=""1""/>
    </svg>
  </div>
  <h1>Ворота</h1>
  <div class=""sub"">Вход в систему</div>
  <form method=""post"" action=""/login"">
    __ERROR__
    <label>Логин</label>
    <input name=""u"" autocomplete=""username"" autofocus>
    <label>Пароль</label>
    <input name=""p"" type=""password"" autocomplete=""current-password"">
    <label style=""display:flex;align-items:center;gap:8px;font-size:13px;color:#565f6b;margin:2px 0 12px 2px""><input type=""checkbox"" name=""remember"" value=""1"" style=""width:auto;margin:0""> Запомнить на 12 месяцев</label>
    <button type=""submit"">Войти</button>
  </form>
  <div class=""foot"">Доступ к дверям СКУД</div>
</div>
</body></html>
";

    const string AppPage = @"<!doctype html>
<html lang=""ru""><head><meta charset=""utf-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Ворота</title>
<style>
:root{--bg:#e3e6ea;--card:#eef0f3;--line:#d6dae0;--acc:#3f8471;--txt:#2a3037;--mut:#565f6b;--muted:#828a95}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;padding:24px 18px 40px}
.wrap{max-width:1080px;margin:0 auto}
header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:4px;flex-wrap:wrap}
h1{font-size:28px;font-weight:600;margin:0;letter-spacing:-.02em}
.who{color:var(--muted);font-size:13px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.who a{color:var(--mut);text-decoration:none;border:1px solid var(--line);background:var(--card);border-radius:10px;padding:8px 12px;font-size:13px}
.who a:hover{color:var(--txt);border-color:#cfd8e3}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;display:flex;flex-direction:column;gap:14px}
.top{display:flex;align-items:center;gap:12px}
.icon{width:42px;height:42px;border-radius:50%;background:#e4ede9;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.name{font-size:16px;font-weight:600;flex:1}
.btns{display:flex;gap:10px}
button{border-radius:11px;padding:11px 14px;font-size:14px;font-weight:600;cursor:pointer;flex:1;transition:.15s;display:flex;align-items:center;justify-content:center;gap:7px}
.bin{background:#e6eee9;border:1px solid #cfddd5;color:#2f6b5b}
.bin:hover{background:#dce8e1}
.bout{background:#e7ebf2;border:1px solid #d2dae6;color:#44699b}
.bout:hover{background:#dce3ee}
button:active{transform:translateY(1px)}
button:disabled{opacity:.55;cursor:default;transform:none}
#toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:#3a424c;color:#eef0f3;padding:12px 20px;border-radius:11px;font-size:14px;opacity:0;transition:.25s;pointer-events:none;box-shadow:0 12px 30px rgba(16,24,40,.18)}
#toast.show{opacity:1}
.empty{color:var(--muted);text-align:center;padding:40px 0}
</style></head><body>
<div class=""wrap"">
  <header>
    <h1>Ворота</h1>
    <div class=""who"">
      <span>__LOGIN__</span>
      __ADMINLINK__
      <a href=""/logout"">Выйти</a>
    </div>
  </header>
  <div class=""sub"" id=""sub"">Загрузка…</div>
  <div id=""list"" class=""grid""></div>
</div>
<div id=""toast""></div>
<script>
var CSRF='__CSRF__';
var ICON='<svg width=""22"" height=""22"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#2f6b5b"" stroke-width=""1.8"" stroke-linecap=""round"" stroke-linejoin=""round""><path d=""M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16""/><path d=""M15 12h5""/><path d=""M2 21h20""/><circle cx=""11"" cy=""12"" r=""1""/></svg>';
var ARR_IN='<svg width=""16"" height=""16"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#2f6b5b"" stroke-width=""2"" stroke-linecap=""round"" stroke-linejoin=""round""><path d=""M5 12h14""/><path d=""M13 6l6 6-6 6""/></svg>';
var ARR_OUT='<svg width=""16"" height=""16"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#44699b"" stroke-width=""2"" stroke-linecap=""round"" stroke-linejoin=""round""><path d=""M19 12H5""/><path d=""M11 6l-6 6 6 6""/></svg>';
function toast(t){var el=document.getElementById('toast');el.textContent=t;el.classList.add('show');clearTimeout(el._t);el._t=setTimeout(function(){el.classList.remove('show');},2400);}
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;}
function iconBox(){var d=el('div','icon');d.innerHTML=ICON;return d;}
async function openDoor(id,dir,name,btn){
  var html=btn.innerHTML;
  btn.disabled=true;btn.textContent='Отправлено…';
  try{
    var r=await fetch('/open',{method:'POST',credentials:'same-origin',
      headers:{'X-CSRF':CSRF,'Content-Type':'application/x-www-form-urlencoded'},
      body:'id='+encodeURIComponent(id)+'&dir='+encodeURIComponent(dir)});
    var o=await r.json();
    if(r.status===401){location.href='/login';return;}
    toast(o.ok?'Открыто: '+name:'Ошибка: '+(o.error||'нет ответа'));
  }catch(e){toast('Ошибка сети');}
  setTimeout(function(){btn.disabled=false;btn.innerHTML=html;},1500);
}
async function load(){
  try{
    var r=await fetch('/doors',{credentials:'same-origin'});
    if(r.status===401){location.href='/login';return;}
    var j=await r.json();
    var list=document.getElementById('list');
    list.innerHTML='';
    var n=0;
    j.doors.forEach(function(d){
      if(!d.readers||!d.readers.length)return;
      n++;
      var c=el('div','card');
      var top=el('div','top');
      top.appendChild(iconBox());
      top.appendChild(el('div','name',d.name));
      c.appendChild(top);
      var b=el('div','btns');
      d.readers.forEach(function(rd){
        var isOut=rd.dir==='out';
        var btn=el('button',isOut?'bout':'bin');
        btn.innerHTML=(isOut?ARR_OUT:ARR_IN)+'<span>'+(isOut?'Выход':'Вход')+'</span>';
        btn.onclick=function(){openDoor(d.id,rd.dir,d.name,btn);};
        b.appendChild(btn);
      });
      c.appendChild(b);
      list.appendChild(c);
    });
    if(!n)list.appendChild(el('div','empty','Двери не настроены на мосте'));
    document.getElementById('sub').textContent='Дверей: '+n+' · обновлено '+new Date().toLocaleTimeString('ru-RU');
  }catch(e){document.getElementById('sub').textContent='Нет связи с мостом';}
}
load();setInterval(load,15000);
</script></body></html>
";

    const string TwoFaPage = @"<!doctype html>
<html lang=""ru""><head><meta charset=""utf-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Двухфакторный вход · Ворота</title>
<style>
:root{--bg:#e3e6ea;--card:#eef0f3;--line:#d6dae0;--acc:#3f8471;--txt:#2a3037;--mut:#565f6b;--muted:#828a95}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.box{width:100%;max-width:420px}
h1{font-size:24px;font-weight:600;text-align:center;margin:0 0 6px}
.sub{color:var(--muted);font-size:13px;text-align:center;margin-bottom:22px}
form,div.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:14px}
label{display:block;font-size:12px;color:var(--mut);margin:0 0 6px 2px;font-weight:500}
input{width:100%;background:#e7eaee;border:1px solid var(--line);color:var(--txt);border-radius:11px;padding:12px 14px;font-size:18px;letter-spacing:.18em;text-align:center;outline:none;font-family:monospace}
input:focus{border-color:var(--acc);background:#fff}
button{width:100%;border:0;border-radius:11px;padding:13px;font-size:15px;font-weight:600;color:#fff;background:var(--acc);cursor:pointer;margin-top:12px}
button.ghost{background:#f2e6e4;color:#a9483f;border:1px solid #e7cfcb}
.err{background:#f2e6e4;border:1px solid #e7cfcb;color:#a9483f;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
.msg{background:#e6eee9;border:1px solid #cfddd5;color:#2f6b5b;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
.secret{font-family:monospace;font-size:19px;letter-spacing:.14em;background:#e7eaee;border:1px dashed #cfd6df;border-radius:10px;padding:12px;text-align:center;word-break:break-all;margin:10px 0}
ol{color:var(--mut);font-size:13px;line-height:1.55;padding-left:18px;margin:10px 0 0}
a.link{display:block;text-align:center;color:var(--mut);font-size:13px;text-decoration:none;margin-top:14px}
a.link:hover{color:var(--txt)}
</style></head><body>
<div class=""box"">
  <h1>__TITLE__</h1>
  <div class=""sub"">__SUBTITLE__</div>
  __BODY__
</div>
</body></html>
";

    const string AdminPage = @"<!doctype html>
<html lang=""ru""><head><meta charset=""utf-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Пользователи · Ворота</title>
<style>
:root{--bg:#e3e6ea;--card:#eef0f3;--line:#d6dae0;--acc:#3f8471;--txt:#2a3037;--mut:#565f6b;--muted:#828a95}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;padding:24px 18px 40px}
.wrap{max-width:900px;margin:0 auto}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px;flex-wrap:wrap}
h1{font-size:26px;font-weight:600;margin:0}
a.btn{color:var(--mut);text-decoration:none;border:1px solid var(--line);background:var(--card);border-radius:10px;padding:8px 12px;font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:16px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 12px;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--muted);font-weight:500}
tr:last-child td{border-bottom:0}
input,select{width:100%;background:#e7eaee;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;color:var(--txt);outline:none}
input:focus,select:focus{border-color:var(--acc)}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.row>div{flex:1;min-width:150px}
button{border-radius:10px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer;border:0;background:var(--acc);color:#fff}
button.mini{background:#f2e6e4;color:#a9483f;border:1px solid #e7cfcb;padding:7px 10px;font-size:13px}
button.mini:hover{background:#eddad7}
.msg{background:#e6eee9;border:1px solid #cfddd5;color:#2f6b5b;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
.err{background:#f2e6e4;border:1px solid #e7cfcb;color:#a9483f;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
pre{white-space:pre-wrap;font-size:12px;color:var(--mut);background:#e7eaee;border:1px solid var(--line);border-radius:10px;padding:12px;max-height:320px;overflow:auto;margin:0}
</style></head><body>
<div class=""wrap"">
  <header>
    <h1>Пользователи</h1>
    <a class=""btn"" href=""/"">← К дверям</a>
  </header>
  __MSG__
  <div class=""card"">
    <h2>Добавить пользователя</h2>
    <form method=""post"" action=""/admin/add""><input type=""hidden"" name=""csrf"" value=""__CSRF__"">
      <div class=""row"">
        <div><input name=""login"" placeholder=""Логин"" autocomplete=""off""></div>
        <div><input name=""pass"" type=""password"" placeholder=""Пароль (мин. 8)"" autocomplete=""new-password""></div>
        <div>
          <select name=""role"">
            <option value=""user"">Пользователь</option>
            <option value=""admin"">Администратор</option>
          </select>
        </div>
        <div style=""flex:0 0 auto""><button type=""submit"">Добавить</button></div>
      </div>
    </form>
  </div>
  <div class=""card"">
    <h2>Список</h2>
    <table>
      <tr><th>Логин</th><th>Роль</th><th>Создан</th><th></th></tr>
      __ROWS__
    </table>
  </div>
  <div class=""card"">
    <h2>Сменить пароль</h2>
    <form method=""post"" action=""/admin/pass""><input type=""hidden"" name=""csrf"" value=""__CSRF__"">
      <div class=""row"">
        <div><input name=""login"" placeholder=""Логин"" autocomplete=""off""></div>
        <div><input name=""pass"" type=""password"" placeholder=""Новый пароль (мин. 8)"" autocomplete=""new-password""></div>
        <div style=""flex:0 0 auto""><button type=""submit"">Сменить</button></div>
      </div>
    </form>
  </div>
  <div class=""card"">
    <h2>Журнал действий</h2>
    <pre>__AUDIT__</pre>
  </div>
</div>
</body></html>
";

    static readonly Dictionary<string, DateTime> Sessions = new Dictionary<string, DateTime>();

    static bool CookieOk(HttpListenerContext ctx)
    {
        try
        {
            var ck = ctx.Request.Cookies["sid"];
            if (ck == null || string.IsNullOrEmpty(ck.Value)) return false;
            lock (Sessions)
            {
                DateTime exp;
                if (!Sessions.TryGetValue(ck.Value, out exp)) return false;
                if (exp < DateTime.UtcNow) { Sessions.Remove(ck.Value); return false; }
                return true;
            }
        }
        catch { return false; }
    }

    static string ReadBody(HttpListenerContext ctx)
    {
        try
        {
            using (var r = new System.IO.StreamReader(ctx.Request.InputStream, Encoding.UTF8))
                return r.ReadToEnd();
        }
        catch { return ""; }
    }

    static string FormValue(string body, string key)
    {
        foreach (string part in body.Split('&'))
        {
            int i = part.IndexOf('=');
            if (i <= 0) continue;
            if (part.Substring(0, i) == key)
                return Uri.UnescapeDataString(part.Substring(i + 1).Replace("+", " "));
        }
        return "";
    }

    static bool BasicAuthOk(HttpListenerContext ctx)
    {
        try
        {
            string h = ctx.Request.Headers["Authorization"];
            if (string.IsNullOrEmpty(h) || !h.StartsWith("Basic ")) return false;
            string decoded = Encoding.UTF8.GetString(Convert.FromBase64String(h.Substring(6).Trim()));
            return decoded == WEB_USER + ":" + WEB_PASS;
        }
        catch { return false; }
    }

    static void RespondHtml(HttpListenerContext ctx, string html)
    {
        try
        {
            byte[] data = Encoding.UTF8.GetBytes(html);
            ctx.Response.StatusCode = 200;
            ctx.Response.ContentType = "text/html; charset=utf-8";
            ctx.Response.ContentLength64 = data.Length;
            ctx.Response.OutputStream.Write(data, 0, data.Length);
            ctx.Response.OutputStream.Close();
        }
        catch { }
    }





    class Pending { public string Login; public DateTime Expires; public bool Remember; }
    static readonly Dictionary<string, Pending> pendingLogins = new Dictionary<string, Pending>();

    /// <summary>Ключ доступа из файла на шаре; null — ключа нет, тогда API закрыт.</summary>
    static string AccessToken()
    {
        try
        {
            string[] paths = { TOKEN_FILE, TOKEN_FILE_FALLBACK };
            foreach (string p in paths)
            {
                if (File.Exists(p))
                {
                    string t = File.ReadAllText(p).Trim();
                    if (t.Length > 0) return t;
                }
            }
        }
        catch { }
        return null;
    }

    /// <summary>Токен API разрешаем только при прямом подключении из локальной сети.
    /// Запрос через прокси приходит с localhost — там нужен реальный IP в X-Forwarded-For.</summary>
    static bool TokenAllowed(HttpListenerContext ctx, string ip)
    {
        try
        {
            string remote = ctx.Request.RemoteEndPoint == null ? "" : ctx.Request.RemoteEndPoint.Address.ToString();
            // Прямое локальное подключение — токен разрешён.
            if (WebAuth.IsTrustedProxy(remote))
            {
                // Через прокси (kp.almak.ru) — только по HTTPS и только с верным токеном.
                return WebAuth.IsHttps(ctx);
            }
            return WebAuth.IsPrivate(remote);
        }
        catch { return false; }
    }

    static string PendingSid(HttpListenerContext ctx)
    {
        var ck = ctx.Request.Cookies["p"];
        return ck == null ? null : ck.Value;
    }

    static string PendingLogin(HttpListenerContext ctx)
    {
        try
        {
            string sid = PendingSid(ctx);
            if (string.IsNullOrEmpty(sid)) return null;
            lock (pendingLogins)
            {
                Pending p;
                if (!pendingLogins.TryGetValue(sid, out p)) return null;
                if (p.Expires < DateTime.UtcNow) { pendingLogins.Remove(sid); return null; }
                return p.Login;
            }
        }
        catch { return null; }
    }

    static string TwoFaPageRender(string title, string subtitle, string body)
    {
        return TwoFaPage.Replace("__TITLE__", title).Replace("__SUBTITLE__", subtitle).Replace("__BODY__", body);
    }

    static void Redirect(HttpListenerContext ctx, string to)
    {
        ctx.Response.StatusCode = 302;
        ctx.Response.AddHeader("Location", to);
        ctx.Response.OutputStream.Close();
    }

    static void SecurityHeaders(HttpListenerContext ctx)
    {
        try
        {
            var h = ctx.Response.Headers;
            h["X-Content-Type-Options"] = "nosniff";
            h["X-Frame-Options"] = "DENY";
            h["Referrer-Policy"] = "no-referrer";
            h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()";
            h["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'";
            h["Cache-Control"] = "no-store, no-cache, must-revalidate";
            if (ctx.Request.IsSecureConnection) h["Strict-Transport-Security"] = "max-age=31536000";
        }
        catch { }
    }

    static string Escape(string s)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;")
                .Replace("\"", "&quot;").Replace("'", "&#39;");
    }

    static string FormField(string body, string key)
    {
        var nv = ParseForm(body);
        return nv[key] ?? "";
    }

    static bool CsrfOk(HttpListenerContext ctx, WebAuth.Session s, string body)
    {
        try
        {
            string h = ctx.Request.Headers["X-CSRF"];
            if (!string.IsNullOrEmpty(h) && h == s.Csrf) return true;
            if (!string.IsNullOrEmpty(body))
            {
                string f = FormField(body, "csrf");
                if (!string.IsNullOrEmpty(f) && f == s.Csrf) return true;
            }
            string origin = ctx.Request.Headers["Origin"];
            if (string.IsNullOrEmpty(origin)) origin = ctx.Request.Headers["Referer"];
            if (!string.IsNullOrEmpty(origin))
            {
                string hostHdr = ctx.Request.Headers["Host"];
                if (!string.IsNullOrEmpty(hostHdr))
                {
                    try
                    {
                        var u = new Uri(origin);
                        string hh = hostHdr.Split(':')[0];
                        if (string.Equals(u.Host, hh, StringComparison.OrdinalIgnoreCase)) return true;
                    }
                    catch { }
                }
            }
            return false;
        }
        catch { return false; }
    }

    static System.Collections.Specialized.NameValueCollection ParseForm(string body)
    {
        var nv = new System.Collections.Specialized.NameValueCollection();
        foreach (string part in (body ?? "").Split('&'))
        {
            int i = part.IndexOf('=');
            if (i <= 0) continue;
            nv[Uri.UnescapeDataString(part.Substring(0, i))] =
                Uri.UnescapeDataString(part.Substring(i + 1).Replace("+", " "));
        }
        return nv;
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
            string ip = WebAuth.ClientIp(ctx);
            // Ключ читаем из файла на каждый запрос — смена без пересборки и перезапуска.
            string accessToken = AccessToken();
            SecurityHeaders(ctx);

            if (path == "/login")
            {
                if (ctx.Request.HttpMethod == "POST")
                {
                    if (WebAuth.RateLimited(ip, null))
                    {
                        WebAuth.Audit("login-blocked", "-", ip, "rate");
                        RespondHtml(ctx, LoginPage.Replace("__ERROR__", "<div class='err'>Слишком много попыток. Подождите 15 минут.</div>"));
                        return;
                    }
                    string body = ReadBody(ctx);
                    string u = FormValue(body, "u").Trim(), pw = FormValue(body, "p");
                    if (WebAuth.RateLimited(ip, u))
                    {
                        WebAuth.Audit("login-blocked", u, ip, "login");
                        RespondHtml(ctx, LoginPage.Replace("__ERROR__", "<div class='err'>Слишком много попыток для этого логина. Подождите 15 минут.</div>"));
                        return;
                    }
                    bool remember = FormValue(body, "remember") == "1";
                    if (WebAuth.Check(u, pw))
                    {
                        if (WebAuth.Has2fa(u))
                        {
                            string psid = Guid.NewGuid().ToString("N");
                            lock (pendingLogins) pendingLogins[psid] = new Pending { Login = u, Expires = DateTime.UtcNow.AddMinutes(5), Remember = remember };
                            WebAuth.Audit("login-pass-ok", u, ip, "2fa");
                            ctx.Response.AddHeader("Set-Cookie", "p=" + psid + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=300"
                                + (WebAuth.IsHttps(ctx) ? "; Secure" : ""));
                            ctx.Response.StatusCode = 302;
                            ctx.Response.AddHeader("Location", "/2fa");
                            ctx.Response.OutputStream.Close();
                            return;
                        }
                        double ttl = remember ? 8760 : 8;   // 8760 ч = 12 месяцев
                        string sidNew = WebAuth.CreateSession(u, ip, ttl);
                        string ck = "s=" + sidNew + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=" + (int)(ttl * 3600)
                            + (WebAuth.IsHttps(ctx) ? "; Secure" : "");
                        ctx.Response.AddHeader("Set-Cookie", ck);
                        WebAuth.Audit("login-ok", u, ip, "");
                        ctx.Response.StatusCode = 302;
                        ctx.Response.AddHeader("Location", "/");
                        ctx.Response.OutputStream.Close();
                        return;
                    }
                    WebAuth.Fail(ip, u);
                    WebAuth.Audit("login-fail", u, ip, "");
                    RespondHtml(ctx, LoginPage.Replace("__ERROR__", "<div class='err'>Неверный логин или пароль</div>"));
                    return;
                }
                string dummy1 = null;
                if (WebAuth.Get(ctx, out dummy1) != null)
                {
                    ctx.Response.StatusCode = 302;
                    ctx.Response.AddHeader("Location", "/");
                    ctx.Response.OutputStream.Close();
                    return;
                }
                RespondHtml(ctx, LoginPage.Replace("__ERROR__", ""));
                return;
            }
            if (path == "/logout")
            {
                string dummy2 = null;
                var sv = WebAuth.Get(ctx, out dummy2);
                if (sv != null) WebAuth.Audit("logout", sv.Login, ip, "");
                WebAuth.Drop(ctx);
                ctx.Response.AddHeader("Set-Cookie", "s=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0");
                ctx.Response.StatusCode = 302;
                ctx.Response.AddHeader("Location", "/login");
                ctx.Response.OutputStream.Close();
                return;
            }

            string dummy3 = null;
            var session = WebAuth.Get(ctx, out dummy3);
            bool lanToken = accessToken != null && q["token"] == accessToken && TokenAllowed(ctx, ip);

            if (path == "" || path == "/index.html")
            {
                if (session == null)
                {
                    ctx.Response.StatusCode = 302;
                    ctx.Response.AddHeader("Location", "/login");
                    ctx.Response.OutputStream.Close();
                    return;
                }
                string page = AppPage.Replace("__CSRF__", session.Csrf)
                                      .Replace("__LOGIN__", Escape(session.Login))
                                      .Replace("__ADMINLINK__", session.Role == "admin"
                                          ? "<a href='/admin'>Пользователи</a>" : "");
                RespondHtml(ctx, page);
                return;
            }


            if (path == "/2fa")
            {
                string pend = PendingLogin(ctx);
                if (pend != null)
                {
                    bool rem = false;
                    string psid0 = PendingSid(ctx);
                    lock (pendingLogins) { Pending pp; if (psid0 != null && pendingLogins.TryGetValue(psid0, out pp)) rem = pp.Remember; }
                    string htmlCode = "<form method='post' action='/2fa/verify'>" +
                        "<label>Код</label><input name='code' inputmode='numeric' maxlength='6' autocomplete='one-time-code' autofocus>" +
                        "<label style='display:flex;align-items:center;gap:8px;font-size:13px;color:#565f6b;margin:2px 0 0 2px'><input type='checkbox' name='remember' value='1' style='width:auto;margin:0'" + (rem ? " checked" : "") + "> Запомнить на 12 месяцев</label>" +
                        "<button type='submit'>Подтвердить</button></form>";
                    RespondHtml(ctx, TwoFaPageRender("Код из приложения", "Введите 6 цифр из Google Authenticator", htmlCode));
                    return;
                }
                if (false)
                {
                    RespondHtml(ctx, TwoFaPageRender("Код из приложения", "Введите 6 цифр из Google Authenticator",
                        "<form method='post' action='/2fa/verify'>" +
                        "<label>Код</label><input name='code' inputmode='numeric' maxlength='6' autocomplete='one-time-code' autofocus>" +
                        "<button type='submit'>Подтвердить</button></form>"));
                    return;
                }
                if (session == null) { Redirect(ctx, "/login"); return; }
                string body2 = "<div class='card'>";
                if (WebAuth.Has2fa(session.Login))
                {
                    body2 += "<div class='msg'>Двухфакторная защита включена</div>" +
                        "<form method='post' action='/2fa/disable'><button class='ghost' type='submit'>Отключить 2FA</button></form>";
                }
                else
                {
                    body2 += "<form method='post' action='/2fa/enable'><button type='submit'>Включить 2FA</button></form>";
                }
                body2 += "</div><a class='link' href='/'>← К дверям</a>";
                RespondHtml(ctx, TwoFaPageRender("Защита аккаунта", Escape(session.Login), body2).Replace("__CSRF__", session.Csrf));
                return;
            }
            if (path == "/2fa/verify" && ctx.Request.HttpMethod == "POST")
            {
                string pend2 = PendingLogin(ctx);
                if (pend2 == null) { Redirect(ctx, "/login"); return; }
                string body2fa = ReadBody(ctx);
                string code = FormValue(body2fa, "code");
                bool remember2 = FormValue(body2fa, "remember") == "1";
                {
                    string ps = PendingSid(ctx);
                    lock (pendingLogins) { Pending pp; if (ps != null && pendingLogins.TryGetValue(ps, out pp) && pp.Remember) remember2 = true; }
                }
                if (WebAuth.TotpOk(WebAuth.TotpOf(pend2), code))
                {
                    double ttl2 = remember2 ? 8760 : 8;  // 12 месяцев
                    string sid2 = WebAuth.CreateSession(pend2, ip, ttl2);
                    WebAuth.Audit("login-ok", pend2, ip, "2fa");
                    string psid2 = PendingSid(ctx);
                    if (!string.IsNullOrEmpty(psid2)) lock (pendingLogins) pendingLogins.Remove(psid2);
                    ctx.Response.AddHeader("Set-Cookie", "s=" + sid2 + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=" + (int)(ttl2 * 3600)
                        + (WebAuth.IsHttps(ctx) ? "; Secure" : ""));
                    Redirect(ctx, "/");
                    return;
                }
                WebAuth.Fail(ip, pend2);
                WebAuth.Audit("2fa-fail", pend2, ip, "");
                RespondHtml(ctx, TwoFaPageRender("Код из приложения", "Введите 6 цифр из Google Authenticator",
                    "<div class='err'>Неверный код</div><form method='post' action='/2fa/verify'>" +
                    "<label>Код</label><input name='code' inputmode='numeric' maxlength='6' autocomplete='one-time-code' autofocus>" +
                    "<button type='submit'>Подтвердить</button></form>"));
                return;
            }
            if (path == "/2fa/enable" && ctx.Request.HttpMethod == "POST")
            {
                if (session == null) { Redirect(ctx, "/login"); return; }
                if (!CsrfOk(ctx, session, ReadBody(ctx))) { Respond(ctx, 403, "{\"ok\":false,\"error\":\"csrf\"}"); return; }
                string secret = WebAuth.NewSecret();
                WebAuth.SetPendingSecret(session.Login, secret);
                string uri = "otpauth://totp/Vorota:" + Uri.EscapeDataString(session.Login) + "?secret=" + secret + "&issuer=Vorota";
                string body3 = "<div class='card'>" +
                    "<div style='font-size:13px;color:#5e6673'>Добавьте в Google Authenticator (или другое приложение) секрет:</div>" +
                    "<div class='secret'>" + secret + "</div>" +
                    "<div style='font-size:12px;color:#8a919c;word-break:break-all'>Или ссылка: " + Escape(uri) + "</div>" +
                    "<ol><li>Откройте приложение-аутентификатор</li><li>«Добавить» → «Ввести ключ вручную»</li>" +
                    "<li>Введите секрет и сохраните</li><li>Введите код ниже</li></ol></div>" +
                    "<form method='post' action='/2fa/confirm'><label>Код из приложения</label>" +
                    "<input name='code' inputmode='numeric' maxlength='6' autocomplete='one-time-code' autofocus>" +
                    "<button type='submit'>Включить</button></form>";
                RespondHtml(ctx, TwoFaPageRender("Включение 2FA", "Шаг 2 из 2", body3));
                return;
            }
            if (path == "/2fa/confirm" && ctx.Request.HttpMethod == "POST")
            {
                if (session == null) { Redirect(ctx, "/login"); return; }
                string code2 = FormValue(ReadBody(ctx), "code");
                if (WebAuth.Enable2fa(session.Login, code2))
                {
                    RespondHtml(ctx, TwoFaPageRender("Готово", "Двухфакторная защита включена",
                        "<div class='card'><div class='msg'>Теперь при входе понадобится код из приложения</div></div><a class='link' href='/'>← К дверям</a>"));
                    return;
                }
                RespondHtml(ctx, TwoFaPageRender("Включение 2FA", "Шаг 2 из 2",
                    "<div class='err'>Неверный код, попробуйте ещё раз</div><form method='post' action='/2fa/confirm'>" +
                    "<label>Код из приложения</label><input name='code' inputmode='numeric' maxlength='6' autocomplete='one-time-code' autofocus>" +
                    "<button type='submit'>Включить</button></form>"));
                return;
            }
            if (path == "/2fa/disable" && ctx.Request.HttpMethod == "POST")
            {
                if (session == null) { Redirect(ctx, "/login"); return; }
                WebAuth.Disable2fa(session.Login);
                RespondHtml(ctx, TwoFaPageRender("Готово", "Двухфакторная защита отключена",
                    "<div class='card'><div class='msg'>2FA отключена</div></div><a class='link' href='/'>← К дверям</a>"));
                return;
            }
            if (path == "/admin" || path.StartsWith("/admin/"))
            {
                if (session == null || session.Role != "admin")
                {
                    ctx.Response.StatusCode = 302;
                    ctx.Response.AddHeader("Location", "/login");
                    ctx.Response.OutputStream.Close();
                    return;
                }
                string msg = "";
                if (ctx.Request.HttpMethod == "POST")
                {
                    string body = ReadBody(ctx);
                    if (!CsrfOk(ctx, session, body))
                    {
                        WebAuth.Audit("csrf-fail", session.Login, ip, path);
                        RespondHtml(ctx, TwoFaPageRender("Форма устарела", "Обновите страницу",
                            "<div class='card'><div class='err'>Сессия или форма устарели. Обновите страницу и попробуйте снова.</div>" +
                            "<a class='link' href='/admin'>← Обновить</a></div>"));
                        return;
                    }
                    if (path == "/admin/add")
                    {
                        string err = WebAuth.AddUser(FormValue(body, "login"), FormValue(body, "pass"), FormValue(body, "role"));
                        msg = err == null
                            ? "<div class='msg'>Пользователь добавлен</div>"
                            : "<div class='err'>" + Escape(err) + "</div>";
                    }
                    else if (path == "/admin/del")
                    {
                        bool ok = WebAuth.DeleteUser(FormValue(body, "login"));
                        msg = ok ? "<div class='msg'>Удалён</div>" : "<div class='err'>Нельзя удалить этого пользователя</div>";
                    }
                    else if (path == "/admin/pass")
                    {
                        bool ok = WebAuth.SetPassword(FormValue(body, "login"), FormValue(body, "pass"));
                        msg = ok ? "<div class='msg'>Пароль изменён</div>" : "<div class='err'>Не удалось: нет такого пользователя или пароль короче 8 символов</div>";
                    }
                }
                var rows = new StringBuilder();
                foreach (var u in WebAuth.All())
                {
                    rows.Append("<tr><td>").Append(Escape(u.Login)).Append("</td><td>")
                        .Append(u.Role == "admin" ? "администратор" : "пользователь").Append("</td><td>")
                        .Append(Escape(u.Created)).Append("</td><td>");
                    if (!string.Equals(u.Login, "vitosamin", StringComparison.OrdinalIgnoreCase))
                        rows.Append("<form method='post' action='/admin/del' style='margin:0'>")
                            .Append("<input type='hidden' name='login' value='").Append(Escape(u.Login)).Append("'>")
                            .Append("<button class='mini' type='submit'>Удалить</button></form>");
                    rows.Append("</td></tr>");
                }
                string html = AdminPage.Replace("__CSRF__", session.Csrf)
                                       .Replace("__ROWS__", rows.ToString())
                                       .Replace("__AUDIT__", Escape(WebAuth.AuditTail(60)))
                                       .Replace("__MSG__", msg);
                RespondHtml(ctx, html);
                return;
            }

            if (path == "/doors" || path == "/status")
            {
                if (session == null && !lanToken) { Respond(ctx, 401, "{\"ok\":false,\"error\":\"auth\"}"); return; }
                if (path == "/status") { Respond(ctx, 200, "{\"state\":\"CLOSED\",\"calibrated\":" + (Map.Count > 0 ? "true" : "false") + "}"); return; }
                Respond(ctx, 200, DoorsJson());
                return;
            }

            if (path == "/open")
            {
                if (ctx.Request.HttpMethod == "POST")
                {
                    if (session == null) { Respond(ctx, 401, "{\"ok\":false,\"error\":\"auth\"}"); return; }
                    string openBody = ReadBody(ctx);
                    if (!CsrfOk(ctx, session, openBody)) { Respond(ctx, 403, "{\"ok\":false,\"error\":\"csrf\"}"); return; }
                    q = ParseForm(openBody);
                }
                else if (!lanToken)
                {
                    Respond(ctx, 403, "{\"ok\":false,\"error\":\"auth\"}");
                    return;
                }
                if (Map.Count == 0) { Respond(ctx, 409, "{\"ok\":false,\"error\":\"not calibrated\"}"); return; }
                int doorId;
                if (!int.TryParse(q["id"] ?? "", out doorId)) { Respond(ctx, 400, "{\"ok\":false,\"error\":\"id\"}"); return; }
                string dir = q["dir"] ?? "";
                var rows2 = new List<int>();
                var seen = new HashSet<int>();
                foreach (var e in Map.Values)
                {
                    if (e.Dev != doorId) continue;
                    if (!seen.Add(e.Rdr)) continue;
                    bool isOut = IsOut(e.Rdr);
                    if (dir == "in" && isOut) continue;
                    if (dir == "out" && !isOut) continue;
                    rows2.Add(e.Row);
                }
                if (rows2.Count == 0) { Respond(ctx, 404, "{\"ok\":false,\"error\":\"door\"}"); return; }
                rows2.Sort();
                WebAuth.Audit("open", session != null ? session.Login : "token", ip, "door=" + doorId + " dir=" + dir);
                Respond(ctx, 200, OpenRows(rows2));
                return;
            }

            if (accessToken == null || q["token"] != accessToken || !WebAuth.IsPrivate(ip))
            {
                Respond(ctx, 401, "{\"ok\":false,\"error\":\"auth\"}");
                return;
            }
            if (path == "/calibrate")
            {
                int fromRow = 1;
                int.TryParse(q["from"] ?? "1", out fromRow);
                Respond(ctx, 200, Calibrate(fromRow));
                return;
            }
            if (path == "/reload") { LoadMap(); Respond(ctx, 200, "{\"ok\":true,\"rows\":" + Map.Count + "}"); return; }
            int id2;
            if (!int.TryParse(q["id"] ?? "", out id2)) { Respond(ctx, 400, "{\"ok\":false,\"error\":\"id\"}"); return; }
            if (path == "/press")
            {
                string btnName = q["btn"] ?? "";
                string label = btnName == "unlock" ? "Разблокировать" : (btnName == "lock" ? "Заблокировать" : "Открыть дверь");
                lock (uiLock)
                {
                    if (!EnsureReady()) { Respond(ctx, 500, "{\"ok\":false,\"error\":\"gate ui not ready\"}"); return; }
                    Focus();
                    if (id2 > 0 && !SelectRow(id2)) { Respond(ctx, 500, "{\"ok\":false,\"error\":\"select failed\"}"); return; }
                    bool ok = PressButton(label);
                    Respond(ctx, 200, "{\"ok\":" + (ok ? "true" : "false") + ",\"button\":\"" + label + "\"}");
                }
                return;
            }
            if (path == "/openrow")
            {
                if (Map.Count == 0) { Respond(ctx, 409, "{\"ok\":false,\"error\":\"not calibrated\"}"); return; }
                Respond(ctx, 200, OpenRows(new List<int> { id2 }));
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
        WebAuth.Init();
        Log("bridge 4.0 start, mapped rows=" + Map.Count);
        var listener = new HttpListener();
        listener.Prefixes.Add("http://+:" + PORT + "/");
        try { listener.Start(); }
        catch (Exception e) { Log("listen err " + e.Message); return; }
        Log("listening " + PORT);
        // прогрев: держим окно готовым и сортировку зафиксированной, чтобы первое нажатие не ждало
        new Thread(() =>
        {
            try
            {
                lock (uiLock)
                {
                    if (EnsureReady())
                    {
                        Focus();
                        ForceSort();
                        sortChecked = true;
                        Log("warmup done");
                    }
                    else Log("warmup skipped: ui not ready");
                }
            }
            catch (Exception e) { Log("warmup err " + e.Message); }
        }) { IsBackground = true }.Start();
        while (true)
        {
            var ctx = listener.GetContext();
            ThreadPool.QueueUserWorkItem(_ => Handle(ctx));
        }
    }
}
