using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;

/// <summary>Пользователи, сессии, защита от подбора, журнал действий.</summary>
static class WebAuth
{
    public class User
    {
        public string Login;
        public string Salt;
        public string Hash;
        public string Role;      // admin | user
        public string Created;
        public long Iter;
        public string Totp;      // base32-секрет, пусто = 2FA выключена
        public string TotpPending;
    }

    public class Session
    {
        public string Login;
        public string Role;
        public DateTime Expires;
        public string Csrf;
        public string Ip;
    }

    class Attempts
    {
        public int Count;
        public DateTime Until;
    }

    const int ITER = 120000;
    const int SESSION_HOURS = 8;
    const int MAX_FAIL_PER_IP = 10;
    const int MAX_FAIL_PER_LOGIN = 5;
    static readonly TimeSpan BLOCK_FOR = TimeSpan.FromMinutes(15);

    static readonly string UsersPath = @"C:\Users\Public\gate_users.json";
    static readonly string AuditPath = @"C:\Users\Public\gate_audit.log";
    static readonly object sync = new object();
    static readonly List<User> users = new List<User>();
    static readonly Dictionary<string, Session> sessions = new Dictionary<string, Session>();
    static readonly Dictionary<string, Attempts> fails = new Dictionary<string, Attempts>();

    public static void Init()
    {
        lock (sync)
        {
            users.Clear();
            if (File.Exists(UsersPath))
            {
                try
                {
                    string body = File.ReadAllText(UsersPath, Encoding.UTF8);
                    foreach (string obj in SplitObjects(body))
                    {
                        var u = new User
                        {
                            Login = Str(obj, "\"login\":\""),
                            Salt = Str(obj, "\"salt\":\""),
                            Hash = Str(obj, "\"hash\":\""),
                            Role = Str(obj, "\"role\":\""),
                            Created = Str(obj, "\"created\":\""),
                            Totp = Str(obj, "\"totp\":\""),
                            TotpPending = Str(obj, "\"totpPending\":\""),
                        };
                        long it;
                        u.Iter = long.TryParse(Str(obj, "\"iter\":"), out it) && it > 0 ? it : ITER;
                        if (!string.IsNullOrEmpty(u.Login) && !string.IsNullOrEmpty(u.Hash)) users.Add(u);
                    }
                }
                catch { }
            }
            if (users.Count == 0)
            {
                AddUserInternal("vitosamin", "Admin910327", "admin");
                Save();
            }
            Audit("start", "-", "-", "users=" + users.Count);
        }
    }

    static IEnumerable<string> SplitObjects(string body)
    {
        int i = 0;
        while (true)
        {
            int a = body.IndexOf('{', i);
            if (a < 0) yield break;
            int b = body.IndexOf('}', a);
            if (b < 0) yield break;
            yield return body.Substring(a, b - a + 1);
            i = b + 1;
        }
    }

    static string Str(string obj, string key)
    {
        int i = obj.IndexOf(key, StringComparison.Ordinal);
        if (i < 0) return "";
        i += key.Length;
        if (key.EndsWith(":"))
        {
            int j = i;
            while (j < obj.Length && (char.IsDigit(obj[j]) || obj[j] == '-')) j++;
            return obj.Substring(i, j - i);
        }
        int e = obj.IndexOf('"', i);
        return e < 0 ? "" : obj.Substring(i, e - i);
    }

    static byte[] Salt()
    {
        var b = new byte[16];
        using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
        return b;
    }

    static string Hash(string pass, byte[] salt, int iter)
    {
        using (var k = new Rfc2898DeriveBytes(pass, salt, iter))
            return Convert.ToBase64String(k.GetBytes(32));
    }

    public static void Save()
    {
        var sb = new StringBuilder("{\"users\":[");
        bool first = true;
        foreach (var u in users)
        {
            if (!first) sb.Append(",");
            first = false;
            sb.Append("{\"login\":\"").Append(u.Login)
              .Append("\",\"salt\":\"").Append(u.Salt)
              .Append("\",\"hash\":\"").Append(u.Hash)
              .Append("\",\"role\":\"").Append(u.Role)
              .Append("\",\"iter\":").Append(u.Iter)
              .Append(",\"created\":\"").Append(u.Created)
              .Append("\",\"totp\":\"").Append(u.Totp ?? "")
              .Append("\",\"totpPending\":\"").Append(u.TotpPending ?? "").Append("\"}");
        }
        sb.Append("]}");
        try
        {
            File.WriteAllText(UsersPath, sb.ToString(), Encoding.UTF8);
        }
        catch (Exception e)
        {
            Audit("save-error", "-", "-", e.Message);
        }
    }

    static void AddUserInternal(string login, string pass, string role)
    {
        var salt = Salt();
        var u = new User
        {
            Login = login,
            Salt = Convert.ToBase64String(salt),
            Hash = Hash(pass, salt, ITER),
            Role = role,
            Created = DateTime.Now.ToString("yyyy-MM-dd HH:mm"),
            Iter = ITER,
        };
        users.Add(u);
    }

    public static bool Exists(string login)
    {
        lock (sync) return users.Exists(u => string.Equals(u.Login, login, StringComparison.OrdinalIgnoreCase));
    }

    public static string AddUser(string login, string pass, string role)
    {
        lock (sync)
        {
            login = (login ?? "").Trim();
            if (login.Length < 3) return "Логин минимум 3 символа";
            if (login.Length > 32) return "Логин слишком длинный";
            if (string.IsNullOrEmpty(pass) || pass.Length < 8) return "Пароль минимум 8 символов";
            if (ExistsInternal(login)) return "Такой пользователь уже есть";
            AddUserInternal(login, pass, role == "admin" ? "admin" : "user");
            Save();
            Audit("user-add", login, "-", role);
            return null;
        }
    }

    static bool ExistsInternal(string login)
    {
        return users.Exists(u => string.Equals(u.Login, login, StringComparison.OrdinalIgnoreCase));
    }

    public static bool DeleteUser(string login)
    {
        lock (sync)
        {
            if (string.Equals(login, "vitosamin", StringComparison.OrdinalIgnoreCase)) return false;
            int n = users.RemoveAll(u => string.Equals(u.Login, login, StringComparison.OrdinalIgnoreCase));
            if (n > 0) { Save(); Audit("user-del", login, "-", "-"); }
            return n > 0;
        }
    }

    public static bool SetPassword(string login, string pass)
    {
        lock (sync)
        {
            if (string.IsNullOrEmpty(pass) || pass.Length < 8) return false;
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null) return false;
            var salt = Salt();
            u.Salt = Convert.ToBase64String(salt);
            u.Hash = Hash(pass, salt, (int)ITER);
            u.Iter = ITER;
            Save();
            Audit("pass-change", login, "-", "-");
            return true;
        }
    }

    public static bool RateLimited(string ip, string login)
    {
        lock (sync)
        {
            Attempts a;
            if (fails.TryGetValue("ip:" + ip, out a) && a.Until > DateTime.UtcNow) return true;
            if (!string.IsNullOrEmpty(login) && fails.TryGetValue("u:" + login.ToLowerInvariant(), out a)
                && a.Until > DateTime.UtcNow) return true;
            return false;
        }
    }

    static void Bump(string key, int max)
    {
        Attempts a;
        if (!fails.TryGetValue(key, out a)) { a = new Attempts(); fails[key] = a; }
        a.Count++;
        if (a.Count >= max) { a.Until = DateTime.UtcNow.Add(BLOCK_FOR); a.Count = 0; }
    }

    public static void Fail(string ip, string login)
    {
        lock (sync)
        {
            Bump("ip:" + ip, MAX_FAIL_PER_IP);
            if (!string.IsNullOrEmpty(login)) Bump("u:" + login.ToLowerInvariant(), MAX_FAIL_PER_LOGIN);
        }
    }

    public static bool Check(string login, string pass)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null) return false;
            byte[] salt;
            try { salt = Convert.FromBase64String(u.Salt); } catch { return false; }
            string calc = Hash(pass ?? "", salt, (int)u.Iter);
            if (!FixedEquals(calc, u.Hash)) return false;
            fails.Remove("u:" + u.Login.ToLowerInvariant());
            return true;
        }
    }

    static bool FixedEquals(string a, string b)
    {
        if (a == null || b == null || a.Length != b.Length) return false;
        int diff = 0;
        for (int i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
        return diff == 0;
    }

    public static string RoleOf(string login)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            return u == null ? "" : u.Role;
        }
    }

    public static List<User> All()
    {
        lock (sync) return new List<User>(users);
    }

    public static string CreateSession(string login, string ip)
    {
        var s = new Session
        {
            Login = login,
            Role = RoleOf(login),
            Expires = DateTime.UtcNow.AddHours(SESSION_HOURS),
            Csrf = Guid.NewGuid().ToString("N"),
            Ip = ip ?? "",
        };
        string sid = Guid.NewGuid().ToString("N");
        lock (sync) sessions[sid] = s;
        return sid;
    }

    public static Session Get(HttpListenerContext ctx, out string sid)
    {
        sid = null;
        try
        {
            var ck = ctx.Request.Cookies["s"];
            if (ck == null || string.IsNullOrEmpty(ck.Value)) return null;
            sid = ck.Value;
            lock (sync)
            {
                Session s;
                if (!sessions.TryGetValue(sid, out s)) return null;
                if (s.Expires < DateTime.UtcNow) { sessions.Remove(sid); return null; }
                s.Expires = DateTime.UtcNow.AddHours(SESSION_HOURS);
                return s;
            }
        }
        catch { return null; }
    }

    public static void Drop(HttpListenerContext ctx)
    {
        try
        {
            var ck = ctx.Request.Cookies["s"];
            if (ck != null) lock (sync) sessions.Remove(ck.Value);
        }
        catch { }
    }

    /// <summary>Адреса, которым доверяем заголовки прокси (сам прокси).</summary>
    static readonly string[] TrustedProxies = { "127.0.0.1", "::1", "::ffff:127.0.0.1", "192.168.2.165" };

    public static bool IsTrustedProxy(string remote)
    {
        foreach (string p in TrustedProxies)
            if (string.Equals(remote, p, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    public static string ForwardedIp(HttpListenerContext ctx)
    {
        try
        {
            string fwd = ctx.Request.Headers["CF-Connecting-IP"];
            if (string.IsNullOrEmpty(fwd)) fwd = ctx.Request.Headers["X-Forwarded-For"];
            if (string.IsNullOrEmpty(fwd)) return "";
            // XFF прокси дописывает в конец: берём последний (его добавил наш прокси),
            // иначе клиент подделает первый элемент.
            string[] parts = fwd.Split(',');
            return parts[parts.Length - 1].Trim();
        }
        catch { return ""; }
    }

    public static string ClientIp(HttpListenerContext ctx)
    {
        try
        {
            string remote = ctx.Request.RemoteEndPoint == null ? "?" : ctx.Request.RemoteEndPoint.Address.ToString();
            // Заголовкам прокси верим только от самого прокси, иначе клиент подделает X-Forwarded-For.
            bool local = IsTrustedProxy(remote);
            if (!local) return remote;
            string fwd = ctx.Request.Headers["CF-Connecting-IP"];
            if (!string.IsNullOrEmpty(fwd)) return fwd.Trim();
            string xff = ctx.Request.Headers["X-Forwarded-For"];
            if (!string.IsNullOrEmpty(xff)) return xff.Split(',')[0].Trim();
            return remote;
        }
        catch { return "?"; }
    }

    /// <summary>Запрос пришёл по HTTPS (напрямую или через локальный прокси).</summary>
    public static bool IsHttps(HttpListenerContext ctx)
    {
        try
        {
            if (ctx.Request.IsSecureConnection) return true;
            string proto = ctx.Request.Headers["X-Forwarded-Proto"];
            if (!string.IsNullOrEmpty(proto) && proto.ToLowerInvariant() == "https")
            {
                string remote = ctx.Request.RemoteEndPoint == null ? "" : ctx.Request.RemoteEndPoint.Address.ToString();
                if (remote == "127.0.0.1" || remote == "::1" || remote == "::ffff:127.0.0.1") return true;
            }
            return false;
        }
        catch { return false; }
    }

    public static bool IsPrivate(string ip)
    {
        try
        {
            if (ip == "::1" || ip == "127.0.0.1") return true;
            var a = IPAddress.Parse(ip);
            byte[] b = a.GetAddressBytes();
            if (b.Length == 4)
            {
                if (b[0] == 10) return true;
                if (b[0] == 192 && b[1] == 168) return true;
                if (b[0] == 172 && b[1] >= 16 && b[1] <= 31) return true;
                if (b[0] == 127) return true;
            }
            if (b.Length == 16) return a.IsIPv6LinkLocal || a.IsIPv6SiteLocal;
            return false;
        }
        catch { return false; }
    }


    // ---------- TOTP (Google Authenticator) ----------
    const string B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

    public static string NumOf(long v) { return v.ToString(); }

    static string Base32(byte[] data)
    {
        var sb = new StringBuilder();
        int bits = 0, value = 0;
        foreach (byte b in data)
        {
            value = (value << 8) | b;
            bits += 8;
            while (bits >= 5)
            {
                sb.Append(B32[(value >> (bits - 5)) & 31]);
                bits -= 5;
            }
        }
        if (bits > 0) sb.Append(B32[(value << (5 - bits)) & 31]);
        return sb.ToString();
    }

    static byte[] FromBase32(string s)
    {
        if (string.IsNullOrEmpty(s)) return new byte[0];
        s = s.Trim().Replace(" ", "").ToUpperInvariant().TrimEnd('=');
        var bytes = new List<byte>();
        int bits = 0, value = 0;
        foreach (char c in s)
        {
            int i = B32.IndexOf(c);
            if (i < 0) continue;
            value = (value << 5) | i;
            bits += 5;
            if (bits >= 8)
            {
                bytes.Add((byte)((value >> (bits - 8)) & 0xFF));
                bits -= 8;
            }
        }
        return bytes.ToArray();
    }

    static string CodeAt(byte[] secret, long step)
    {
        byte[] counter = BitConverter.GetBytes(step);
        if (BitConverter.IsLittleEndian) Array.Reverse(counter);
        using (var h = new HMACSHA1(secret))
        {
            byte[] hash = h.ComputeHash(counter);
            int off = hash[hash.Length - 1] & 0x0F;
            int bin = ((hash[off] & 0x7F) << 24) | ((hash[off + 1] & 0xFF) << 16)
                    | ((hash[off + 2] & 0xFF) << 8) | (hash[off + 3] & 0xFF);
            return (bin % 1000000).ToString("D6");
        }
    }

    public static bool TotpOk(string secret, string code)
    {
        if (string.IsNullOrEmpty(secret) || string.IsNullOrEmpty(code)) return false;
        code = code.Trim().Replace(" ", "");
        if (code.Length != 6) return false;
        byte[] key = FromBase32(secret);
        if (key.Length == 0) return false;
        long step = DateTimeOffset.UtcNow.ToUnixTimeSeconds() / 30;
        for (long d = -1; d <= 1; d++)
            if (FixedEquals(CodeAt(key, step + d), code)) return true;
        return false;
    }

    public static string NewSecret()
    {
        var b = new byte[20];
        using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
        return Base32(b);
    }

    public static string TotpOf(string login)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            return u == null ? null : (u.Totp ?? "");
        }
    }

    public static bool Has2fa(string login)
    {
        return !string.IsNullOrEmpty(TotpOf(login));
    }

    public static void SetPendingSecret(string login, string secret)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null) return;
            u.TotpPending = secret ?? "";
            Save();
        }
    }

    public static string GetPendingSecret(string login)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            return u == null ? "" : (u.TotpPending ?? "");
        }
    }

    public static bool Enable2fa(string login, string code)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null || string.IsNullOrEmpty(u.TotpPending)) return false;
            if (!TotpOk(u.TotpPending, code)) return false;
            u.Totp = u.TotpPending;
            u.TotpPending = "";
            Save();
            Audit("2fa-on", login, "-", "");
            return true;
        }
    }

    public static bool Disable2fa(string login)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null) return false;
            u.Totp = "";
            u.TotpPending = "";
            Save();
            Audit("2fa-off", login, "-", "");
            return true;
        }
    }

    public static string Role2fa(string login)
    {
        lock (sync)
        {
            var u = users.Find(x => string.Equals(x.Login, login, StringComparison.OrdinalIgnoreCase));
            if (u == null) return "";
            return string.IsNullOrEmpty(u.Totp) ? "off" : "on";
        }
    }

    public static void Audit(string action, string login, string ip, string detail)
    {
        try
        {
            File.AppendAllText(AuditPath,
                DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | " + action + " | " + login + " | " + ip + " | " + detail + Environment.NewLine,
                Encoding.UTF8);
        }
        catch { }
    }

    public static string AuditTail(int lines)
    {
        try
        {
            if (!File.Exists(AuditPath)) return "";
            string[] all = File.ReadAllLines(AuditPath, Encoding.UTF8);
            int n = Math.Min(lines, all.Length);
            var sb = new StringBuilder();
            for (int i = all.Length - n; i < all.Length; i++) sb.Append(all[i]).Append("\n");
            return sb.ToString();
        }
        catch { return ""; }
    }
}
