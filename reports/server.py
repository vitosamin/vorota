#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""СКУД Gate — веб-сервис мониторинга и отчётов.

Запуск:  python3 server.py [порт]        (по умолчанию 8095 из gate.config.json)
Вход:    логин/пароль из gate.config.json → auth (по умолчанию vitosamin)

Возможности:
    • вход по логину/паролю, сессия в подписанной cookie (12 часов);
    • мониторинг вживую: Server-Sent Events (/api/stream) + опрос;
    • отчёты посещаемости, графики, выгрузка в 1С (CSV cp1251) и Excel.
"""

import base64
import csv
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import accounts
import gate

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
PORT = int(os.environ.get("GATE_PORT") or gate.CFG.get("port", 8095))

AUTH = gate.CFG.get("auth", {})
AUTH_USER = AUTH.get("user", "vitosamin")
AUTH_PASS = AUTH.get("password", "Admin910327")
REALM = AUTH.get("realm", "SKUD Gate")
SESSION_HOURS = int(AUTH.get("session_hours", 12))
SECRET = (gate.CFG.get("secret") or "gate-skud-secret").encode("utf-8")
COOKIE = "gate_session"

def qpoints(q):
    """Выбранные контрольные точки: `points=A|B` или одиночный `point`."""
    return q.get("points") or q.get("point") or None


def page_version():
    """Версия интерфейса — меняется при каждой правке index.html."""
    try:
        st = os.stat(os.path.join(WEB, "index.html"))
        return "%d-%d" % (int(st.st_mtime), int(st.st_size))
    except OSError:
        return "0"


sync_lock = threading.Lock()
last_sync = {"at": None, "result": None, "error": None}


# --------------------------------------------------------------------------
# авторизация
# --------------------------------------------------------------------------

def make_token(user):
    exp = int(time.time()) + SESSION_HOURS * 3600
    payload = "%s|%d" % (user, exp)
    sig = hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return "%s|%s" % (payload, sig)


def check_token(token):
    if not token or token.count("|") != 2:
        return None
    user, exp, sig = token.rsplit("|", 2)
    payload = "%s|%s" % (user, exp)
    good = hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(good, sig):
        return None
    try:
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    return user


def parse_cookies(header):
    out = {}
    for part in (header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def check_password(user, password):
    return accounts.verify(user, password)


# --------------------------------------------------------------------------
# автосинхронизация
# --------------------------------------------------------------------------

def do_sync(days=None):
    if not sync_lock.acquire(blocking=False):
        return {"busy": True}
    try:
        con = gate.connect()
        gate.init_db(con)
        today = dt.date.today()
        if days is None:
            res = gate.sync_events(today.isoformat(), today.isoformat(), con=con)
            tick = str(int(time.time() // 600))
            if gate.meta_get(con, "_cfg_tick", "0") != tick:
                gate.sync_config(con=con)
                gate.meta_set(con, "_cfg_tick", tick)
                con.commit()
        else:
            gate.sync_config(con=con)
            start = today - dt.timedelta(days=max(0, int(days)))
            res = gate.sync_events(start.isoformat(), today.isoformat(), con=con)
        try:
            gate.expire_passes(con)              # истёкшие пропуска — убрать ключи
        except Exception:                        # noqa: BLE001
            pass
        con.close()
        last_sync.update({"at": dt.datetime.now().isoformat(timespec="seconds"),
                          "result": res, "error": None})
        return res
    except Exception as exc:                     # noqa: BLE001
        last_sync.update({"at": dt.datetime.now().isoformat(timespec="seconds"),
                          "error": str(exc)})
        return {"error": str(exc)}
    finally:
        sync_lock.release()


def sync_worker():
    while True:
        try:
            do_sync()
        except Exception:                        # noqa: BLE001
            pass
        time.sleep(45)


# --------------------------------------------------------------------------
# выгрузки
# --------------------------------------------------------------------------

COLS_1C = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("day", "Дата"),
    ("enter", "Приход"),
    ("exit", "Уход"),
    ("hours", "Часов"),
    ("passes", "Проходов"),
    ("late", "ОпозданиеМин"),
    ("early", "РаннийУходМин"),
    ("points", "КонтрольныеТочки"),
]

COLS_SUM = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("days", "Дней"),
    ("hours", "Часов"),
    ("avg_hours", "СреднеВДень"),
    ("passes", "Проходов"),
    ("late_days", "ДнейСОпозданием"),
    ("late_total", "ОпозданиеМинВсего"),
]

COLS_USERS = [
    ("number", "ТабельныйНомер"), ("fio", "ФИО"), ("group", "Подразделение"),
    ("position", "Должность"), ("status", "Статус"),
    ("last_day", "ПоследнийПроходДата"), ("last_used", "ПоследнийПроходВремя"),
    ("last_unit", "Точка"),
]

COLS_EVENTS = [
    ("day", "Дата"), ("time", "Время"), ("type_title", "Тип"), ("unit", "Точка"),
    ("message", "Событие"), ("name", "Сотрудник"), ("alarm_flag", "Тревога"),
]

COLS_LATE = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("late_days", "ДнейСОпозданием"),
    ("late_total", "ОпозданиеМинВсего"),
    ("avg_late", "СреднееОпозданиеМин"),
    ("max_late", "МаксимальноеОпозданиеМин"),
    ("worst_day", "ХудшийДень"),
    ("worst_time", "ПриходВХудшийДень"),
]

COLS_ABS = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("days", "ДнейВПериоде"),
    ("passes", "Проходов"),
]

# Заголовки для печати и Excel — человеческие, с пробелами.
# В CSV для 1С остаются «слитные» имена: это формат обмена, его не трогаем.
PRETTY_COLS = {
    "ТабельныйНомер": "Табельный номер",
    "ФИО": "ФИО",
    "Подразделение": "Подразделение",
    "Должность": "Должность",
    "Дата": "Дата",
    "Время": "Время",
    "Приход": "Приход",
    "Уход": "Уход",
    "Часов": "Часов",
    "Проходов": "Проходов",
    "ОпозданиеМин": "Опоздание, мин",
    "РаннийУходМин": "Ранний уход, мин",
    "КонтрольныеТочки": "Контрольные точки",
    "Дней": "Дней",
    "СреднеВДень": "Средне в день",
    "ДнейСОпозданием": "Дней с опозданием",
    "ОпозданиеМинВсего": "Минут опозданий",
    "СреднееОпозданиеМин": "Среднее опоздание, мин",
    "МаксимальноеОпозданиеМин": "Максимум за раз, мин",
    "ХудшийДень": "Худший день",
    "ПриходВХудшийДень": "Приход в худший день",
    "ПоследнийПроходДата": "Последний проход",
    "ПоследнийПроходВремя": "Время",
    "Точка": "Точка",
    "Статус": "Статус",
    "Тип": "Тип",
    "Событие": "Событие",
    "Сотрудник": "Сотрудник",
    "Тревога": "Тревога",
    "ДнейВПериоде": "Дней в периоде",
}

NUM_KEYS = {"enter", "exit", "hours", "passes", "late", "early", "day", "days",
            "avg_hours", "late_days", "late_total", "avg_late", "max_late",
            "time", "alarm_flag"}


def col_title(t):
    return PRETTY_COLS.get(t, t)


def rows_to_delimited(rows, cols, sep=";", enc="cp1251", dec=",", header=True, quotes=True):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, quoting=csv.QUOTE_ALL if quotes else csv.QUOTE_MINIMAL,
                   lineterminator="\r\n")
    if header:
        w.writerow([title for _, title in cols])
    for r in rows:
        line = []
        for key, _ in cols:
            v = r.get(key, "")
            if v is None:
                v = ""
            if key in ("hours", "avg_hours") and isinstance(v, float):
                v = ("%.2f" % v).replace(".", dec)
            line.append(v)
        w.writerow(line)
    text = buf.getvalue()
    data = text.encode(enc, "replace")
    if enc.lower().replace("-", "") == "utf8":
        data = b"\xef\xbb\xbf" + data
    return data


def rows_to_xls(rows, cols, title):
    """HTML-таблица с mso-стилями — Excel открывает с оформлением."""
    def esc(v):
        return (str(v if v is not None else "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    style = (
        "<style>"
        "table{border-collapse:collapse}"
        "th{background:#1f6feb;color:#fff;padding:6px 10px;border:1px solid #b6c2cf;"
        "font-family:'Segoe UI',Arial;font-size:12px}"
        "td{padding:4px 8px;border:1px solid #d5dde6;font-family:'Segoe UI',Arial;font-size:12px}"
        "td.n{text-align:center}tr.e td{background:#f4f7fb}"
        "h3{font-family:'Segoe UI',Arial;font-size:14px}"
        "</style>"
    )
    head = "".join('<th%s>%s</th>' % (' class="n"' if k in NUM_KEYS else "", esc(col_title(t)))
                   for k, t in cols)
    body = []
    for i, r in enumerate(rows):
        tds = []
        for key, _ in cols:
            v = r.get(key, "")
            if key in ("hours", "avg_hours") and isinstance(v, float):
                v = ("%.2f" % v).replace(".", ",")
            cls = ' class="n"' if key in ("enter", "exit", "hours", "passes", "late", "early",
                                          "day", "days", "avg_hours") else ""
            tds.append("<td%s>%s</td>" % (cls, esc(v)))
        body.append('<tr%s>%s</tr>' % (' class="e"' if i % 2 else "", "".join(tds)))
    return ('<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8">'
            + style + '</head><body><h3>' + esc(title) + '</h3>'
            '<table><thead><tr>' + head + '</tr></thead><tbody>' + "".join(body)
            + '</tbody></table></body></html>').encode("utf-8")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def _esc(v):
    return (str(v if v is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

class Handler(BaseHTTPRequestHandler):
    server_version = "GateSkud/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # -- утилиты ---------------------------------------------------------
    def q(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    def current_user(self):
        user = check_token(parse_cookies(self.headers.get("Cookie")).get(COOKIE))
        if user:
            # пользователя могли удалить или сменить ему логин — сессия недействительна
            return user if accounts.get(user) else None
        hdr = self.headers.get("Authorization") or ""
        if hdr.startswith("Basic "):
            try:
                raw = base64.b64decode(hdr[6:]).decode("utf-8", "replace")
                u, _, p = raw.partition(":")
                if check_password(u, p) and accounts.get(u):
                    return u
            except Exception:                    # noqa: BLE001
                pass
        return None

    def send_bytes(self, data, ctype, filename=None, ascii_name=None, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        if filename:
            disp = "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (
                ascii_name or "report.csv", urllib.parse.quote(filename))
            self.send_header("Content-Disposition", disp)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8", code=code)

    def redirect(self, to, cookie=None):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    # -- GET -------------------------------------------------------------
    def do_GET(self):
        path, q = self.q()
        try:
            if path == "/login":
                return self.serve_static("login.html", ctype="text/html; charset=utf-8")
            if path == "/logout":
                return self.redirect("/login", cookie="%s=; Path=/; Max-Age=0; HttpOnly" % COOKIE)
            if path == "/favicon.ico":
                return self.send_bytes(b"", "image/x-icon")

            user = self.current_user()
            if not user:
                if path.startswith("/api/") or path.startswith("/export/"):
                    return self.send_json({"error": "unauthorized"}, code=401)
                return self.redirect("/login")

            if path in ("/", "/index.html"):
                return self.serve_static("index.html")
            if path.startswith("/static/"):
                return self.serve_static(path[len("/static/"):])
            if path == "/api/passes":
                return self.api_passes(q)
            if path == "/api/gate/find":
                return self.api_gate_find(q)
            if path == "/api/passes/check":
                return self.api_pass_check(q)
            if path == "/api/doors":
                return self.send_json(gate.doors_list(gate.connect()))
            if path == "/print/pass":
                return self.print_pass(q)
            if path == "/print/timesheet":
                return self.print_timesheet(q)
            if path == "/api/me":
                return self.api_me()
            if path == "/api/accounts":
                return self.api_accounts()
            if path == "/api/version":
                return self.send_json({"version": page_version()})
            if path == "/api/status":
                return self.api_status()
            if path == "/api/kpi":
                return self.api_kpi(q)
            if path == "/api/live":
                return self.api_live(q)
            if path == "/api/stream":
                return self.api_stream(q)
            if path == "/api/presence":
                return self.api_presence(q)
            if path == "/api/points":
                return self.api_points()
            if path == "/api/groups":
                return self.api_groups()
            if path == "/api/report":
                return self.api_report(q)
            if path == "/api/timesheet":
                return self.api_timesheet(q)
            if path == "/api/analytics":
                return self.api_analytics(q)
            if path == "/api/events/summary":
                return self.api_events_summary(q)
            if path == "/api/events/list":
                return self.api_events_list(q)
            if path == "/api/late":
                return self.api_late(q)
            if path == "/api/person":
                return self.api_person(q)
            if path == "/api/users":
                return self.api_users(q)
            if path == "/api/employees":
                return self.api_employees(q)
            if path == "/api/reports/preview":
                return self.api_reports_preview(q)
            if path == "/export/users.csv":
                return self.export_users(q, "csv")
            if path == "/export/users.xls":
                return self.export_users(q, "xls")
            if path == "/export/events.csv":
                return self.export_events(q)
            if path == "/api/sync":
                return self.send_json(do_sync(days=q.get("days")))
            if path == "/export/1c.csv":
                return self.export_1c(q)
            if path == "/export/report.xls":
                return self.export_xls(q)
            if path == "/export/timesheet.xls":
                return self.export_timesheet_xls(q)
            if path == "/print":
                return self.export_print(q)
            return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                return self.send_json({"error": str(exc)}, code=500)
            except Exception:                     # noqa: BLE001
                pass

    def serve_static(self, name, ctype=None):
        name = name.replace("..", "")
        full = os.path.join(WEB, name)
        if not os.path.isfile(full):
            return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)
        ctype = ctype or {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
                          "js": "application/javascript; charset=utf-8",
                          "svg": "image/svg+xml", "png": "image/png",
                          "ico": "image/x-icon"}.get(name.rsplit(".", 1)[-1],
                                                     "application/octet-stream")
        with open(full, "rb") as fh:
            return self.send_bytes(fh.read(), ctype)

    # -- API -------------------------------------------------------------
    def api_status(self):
        con = gate.connect()
        gate.init_db(con)
        st = gate.db_status(con)
        con.close()
        st.update({"version": page_version(),
                   "last_sync": last_sync, "server_time": dt.datetime.now().isoformat(timespec="seconds"),
                   "shift_start": gate.CFG.get("shift_start"), "shift_end": gate.CFG.get("shift_end")})
        return self.send_json(st)

    def api_kpi(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        data = gate.kpi(con, day)
        con.close()
        return self.send_json(data)

    def api_live(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        limit = min(500, int(q.get("limit", 60)))
        feed = gate.live_feed(con, day=day, limit=limit, only_passes=(q.get("all") != "1"))
        con.close()
        return self.send_json({"day": day, "items": feed})

    def api_presence(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        people = gate.presence_now(con, day)
        con.close()
        return self.send_json({"day": day, "count": len(people), "people": people})

    def api_points(self):
        con = gate.connect()
        data = gate.points_list(con)
        con.close()
        return self.send_json(data)

    def api_groups(self):
        con = gate.connect()
        data = gate.groups_list(con)
        con.close()
        return self.send_json(data)

    def api_report(self, q):
        frm = q.get("from") or dt.date.today().isoformat()
        to = q.get("to") or frm
        view = q.get("view", "detail")
        con = gate.connect()
        if view == "absent":
            rows = gate.absent(con, frm, to, group=q.get("group"), search=q.get("search"),
                               user_ptr=q.get("user_ptr") or None, point=qpoints(q))
            con.close()
            return self.send_json({"from": frm, "to": to, "view": view, "count": len(rows),
                                   "people": len(rows), "total_hours": 0, "late_days": 0,
                                   "rows": rows, "summary": rows})
        if view == "late":
            items = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                     shift_start=q.get("shift_start"), shift_end=q.get("shift_end"),
                                     user_ptr=q.get("user_ptr") or None, point=qpoints(q))
            con.close()
            return self.send_json({"from": frm, "to": to, "view": view, "count": len(items),
                                   "people": len(items),
                                   "total_hours": 0,
                                   "late_days": sum(x["late_days"] for x in items),
                                   "rows": items, "summary": items})
        rows = gate.attendance(con, frm, to, group=q.get("group"), search=q.get("search"),
                               point=qpoints(q), include_deleted=q.get("deleted") == "1",
                               include_visitors=q.get("visitors") == "1",
                               shift_start=q.get("shift_start"), shift_end=q.get("shift_end"),
                               user_ptr=q.get("user_ptr") or None)
        summary = gate.attendance_summary(rows)
        con.close()
        return self.send_json({
            "from": frm, "to": to, "view": view,
            "count": len(rows), "people": len(summary),
            "total_hours": round(sum(r["hours"] or 0 for r in rows), 2),
            "late_days": sum(1 for r in rows if r["late"]),
            "rows": rows if view == "detail" else [],
            "summary": summary,
        })

    def api_analytics(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.analytics(con, frm, to, group=q.get("group"), point=qpoints(q))
        con.close()
        return self.send_json(data)

    def api_late(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        items = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                 shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
        con.close()
        return self.send_json({"from": frm, "to": to, "count": len(items), "items": items})

    def api_person(self, q):
        try:
            uid = int(q.get("user_ptr", "0"))
        except ValueError:
            return self.send_json({"error": "user_ptr"}, code=400)
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=29)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.person_history(con, uid, frm, to)
        con.close()
        if data is None:
            return self.send_json({"error": "not found"}, code=404)
        return self.send_json(data)

    def api_employees(self, q):
        con = gate.connect()
        items = gate.employees(con, group=q.get("group"))
        con.close()
        return self.send_json({"count": len(items), "items": items})

    def api_users(self, q):
        con = gate.connect()
        items = gate.users_report(con, group=q.get("group"), search=q.get("search"),
                                  include_deleted=q.get("deleted") == "1",
                                  user_ptr=q.get("user_ptr") or None)
        con.close()
        return self.send_json({"count": len(items), "items": items})

    def api_reports_preview(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        up = q.get("user_ptr") or None
        rows = gate.attendance(con, frm, to, group=q.get("group"), point=qpoints(q), user_ptr=up)
        summary = gate.attendance_summary(rows)
        late = sum(1 for a in summary if a["late_total"])
        absent = len(gate.absent(con, frm, to, group=q.get("group"), user_ptr=up, point=qpoints(q)))
        users = len(gate.users_report(con, group=q.get("group"), user_ptr=up))
        events = con.execute("SELECT COUNT(*) c FROM events WHERE day BETWEEN ? AND ?",
                             (frm, to)).fetchone()["c"]
        con.close()
        return self.send_json({"from": frm, "to": to, "urv": len(rows), "summary": len(summary),
                               "late": late, "absent": absent, "users": users, "events": events})

    def export_users(self, q, fmt):
        con = gate.connect()
        rows = gate.users_report(con, group=q.get("group"), search=q.get("search"),
                                 include_deleted=q.get("deleted") == "1",
                                 user_ptr=q.get("user_ptr") or None)
        con.close()
        cols = COLS_USERS
        if fmt == "xls":
            data = rows_to_xls(rows, cols, "Отчёт о пользователях СКУД Gate")
            return self.send_bytes(data, "application/vnd.ms-excel; charset=utf-8",
                                   filename="Пользователи_СКУД.xls", ascii_name="users_skud.xls")
        data = rows_to_delimited(rows, cols, sep=";", enc="cp1251", dec=",")
        return self.send_bytes(data, "text/csv; charset=cp1251",
                               filename="Пользователи_СКУД.csv", ascii_name="users_skud.csv")

    def export_events(self, q):
        frm = q.get("from") or dt.date.today().isoformat()
        to = q.get("to") or frm
        enc = q.get("enc", "cp1251")
        sep = {"tab": "\t", "comma": ",", "semicolon": ";"}.get(q.get("sep", "semicolon"), ";")
        con = gate.connect()
        data, n = gate.events_csv(con, frm, to,
                                  etype=q.get("type") or None,
                                  search=(q.get("search") or "").strip() or None,
                                  message=(q.get("message") or "").strip() or None,
                                  user_ptr=q.get("user_ptr") or None,
                                  point=qpoints(q),
                                  alarms_only=q.get("alarms") == "1",
                                  sep=sep, enc=enc)
        con.close()
        if n == 0:
            data = ("Событий за период %s — %s нет\r\n" % (frm, to)).encode(enc, "replace")
        return self.send_bytes(data, "text/csv; charset=%s" % enc,
                               filename="События_СКУД_%s_%s.csv" % (frm, to),
                               ascii_name="events_%s_%s.csv" % (frm, to))

    def api_passes(self, q):
        con = gate.connect()
        items = gate.passes_list(con, from_day=q.get("from"), to_day=q.get("to"),
                                 state=q.get("state"), search=q.get("search"))
        try:
            idx = gate.gate_index(con)
            for it in items:
                it["gate"] = gate.pass_gate_status(con, it, idx)
        except Exception:                        # noqa: BLE001
            for it in items:
                it["gate"] = None
        info = {"mtime": gate.meta_get(con, "config_mtime", ""),
                "users": int(gate.meta_get(con, "config_users", "0") or 0),
                "synced": gate.meta_get(con, "config_synced", "")}
        con.close()
        counts = {}
        for it in items:
            counts[it["state"]] = counts.get(it["state"], 0) + 1
        return self.send_json({"count": len(items), "items": items, "counts": counts,
                               "gate_info": info})

    def api_gate_find(self, q):
        con = gate.connect()
        data = gate.find_cards(con, (q.get("q") or "").strip())
        con.close()
        return self.send_json(data)

    def api_pass_check(self, q):
        try:
            pid = int(q.get("id", "0"))
        except ValueError:
            pid = 0
        con = gate.connect()
        p = gate.pass_get(con, pid)
        data = gate.pass_gate_status(con, p) if p else None
        con.close()
        if not p:
            return self.send_json({"error": "пропуск не найден"}, code=404)
        return self.send_json({"ok": True, "gate": data, "pass": p})

    def passes_post(self, path, body):
        need = ("admin",) if path == "/api/passes/delete" else ("admin", "operator")
        user = self.require_role(*need)
        if not user:
            return
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = {}
        con = gate.connect()
        try:
            if path == "/api/passes/add":
                p = gate.pass_create(con, payload, created_by=user)
                return self.send_json({"ok": True, "pass": p})
            if path == "/api/passes/revoke":
                p = gate.pass_revoke(con, payload.get("id"))
                return self.send_json({"ok": True, "pass": p})
            if path == "/api/passes/delete":
                gate.pass_delete(con, payload.get("id"))
                return self.send_json({"ok": True})
            return self.send_json({"error": "not found"}, code=404)
        except (ValueError, TypeError) as exc:
            return self.send_json({"ok": False, "error": str(exc)}, code=400)
        finally:
            con.close()

    def print_pass(self, q):
        try:
            pid = int(q.get("id", "0"))
        except ValueError:
            pid = 0
        con = gate.connect()
        p = gate.pass_get(con, pid)
        con.close()
        if not p:
            return self.send_bytes(b"pass not found", "text/plain; charset=utf-8", code=404)

        def esc(v):
            return (str(v if v is not None else "")
                    .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        doors = ", ".join(p.get("doors") or []) or "—"
        html = PASS_TEMPLATE.format(
            number=esc(p["number"]), visitor=esc(p["visitor"]), org=esc(p.get("org") or "—"),
            position=esc(p.get("position") or "—"), schedule=esc(p.get("schedule_text") or "—"),
            card=esc(p.get("card") or "—"),
            document=esc(p.get("document") or "—"), phone=esc(p.get("phone") or "—"),
            host=esc(p.get("host") or "—"), purpose=esc(p.get("purpose") or "—"),
            visit=esc(p.get("visit_date") or ""), valid_to=esc(p.get("valid_to") or ""),
            doors=esc(doors), state=esc(p["state_title"]), note=esc(p.get("note") or ""),
            created=esc((p.get("created_at") or "")[:16].replace("T", " ")),
            author=esc(p.get("created_by") or ""),
            stamp=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
        return self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def api_me(self):
        user = self.current_user()
        if not user:
            return self.send_json({"error": "unauthorized"}, code=401)
        acc = accounts.get(user) or {}
        role = accounts.role_of(user)
        return self.send_json({"login": user, "role": role,
                               "roleTitle": accounts.ROLE_TITLES.get(role, "—"),
                               "name": acc.get("name", user),
                               "gate_user": gate.SMB_USER if role == "admin" else None})

    def api_accounts(self):
        if not self.require_admin():
            return
        return self.send_json({"items": accounts.public(),
                               "roles": [{"id": r, "title": accounts.ROLE_TITLES[r]} for r in accounts.ROLES]})

    def require_admin(self):
        return self.require_role("admin")

    def require_role(self, *roles):
        user = self.current_user()
        if not user:
            self.send_json({"error": "нужно войти"}, code=401)
            return None
        if accounts.role_of(user) not in roles:
            self.send_json({"error": "недостаточно прав"}, code=403)
            return None
        return user

    def admin_post(self, path, body):
        user = self.require_admin()
        if not user:
            return
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = {}
        try:
            if path == "/api/accounts/add":
                accounts.add(payload.get("login"), payload.get("password"),
                             payload.get("role") or "viewer", payload.get("name"))
                return self.send_json({"ok": True, "items": accounts.public()})
            if path == "/api/accounts/delete":
                accounts.delete(payload.get("login"))
                return self.send_json({"ok": True, "items": accounts.public()})
            if path == "/api/accounts/password":
                accounts.set_password(payload.get("login"), payload.get("password"))
                return self.send_json({"ok": True})
            if path == "/api/accounts/role":
                accounts.set_role(payload.get("login"), payload.get("role"))
                return self.send_json({"ok": True, "items": accounts.public()})
            if path == "/api/accounts/name":
                accounts.set_name(payload.get("login"), payload.get("name"))
                return self.send_json({"ok": True, "items": accounts.public()})
            if path == "/api/settings/check-gate":
                ok, msg = gate.check_smb()
                return self.send_json({"ok": ok, "message": msg})
            if path == "/api/settings/gate":
                login = (payload.get("user") or "").strip()
                pwd = payload.get("password") or ""
                if not login or not pwd:
                    return self.send_json({"ok": False, "error": "заполните логин и пароль"}, code=400)
                old_user, old_pass = gate.SMB_USER, gate.SMB_PASS
                gate.set_smb_credentials(login, pwd)
                ok, msg = gate.check_smb()
                if not ok:
                    gate.set_smb_credentials(old_user, old_pass)
                    return self.send_json({"ok": False, "error": "Gate не принял учётку: " + msg}, code=400)
                return self.send_json({"ok": True, "message": msg})
            if path == "/api/settings/password":
                old = payload.get("old") or ""
                new = payload.get("new") or ""
                if not accounts.verify(user, old):
                    return self.send_json({"ok": False, "error": "текущий пароль неверен"}, code=400)
                accounts.set_password(user, new)
                return self.send_json({"ok": True})
            return self.send_json({"error": "not found"}, code=404)
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, code=400)

    def api_events_summary(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.events_summary(con, frm, to)
        con.close()
        return self.send_json(data)

    def api_events_list(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.events_list(
            con, frm, to,
            etype=q.get("type") or None,
            search=(q.get("search") or "").strip() or None,
            message=(q.get("message") or "").strip() or None,
            user_ptr=q.get("user_ptr") or None,
            point=qpoints(q),
            alarms_only=(q.get("alarms") == "1"),
            limit=max(1, min(500, int(q.get("limit", 200)))),
            offset=max(0, int(q.get("offset", 0))))
        con.close()
        return self.send_json(data)

    # -- живой поток (SSE) ------------------------------------------------
    def api_stream(self, q):
        day = q.get("day") or dt.date.today().isoformat()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        con = gate.connect()
        users = gate._user_names(con)

        def item_of(r):
            u = users.get(r["user_ptr"])
            return {"ts": r["ts"], "time": r["ts"][11:19], "user_ptr": r["user_ptr"],
                    "fio": u["fio"] if u else (r["name"] or "—"),
                    "group": u["group"] if u else "", "unit": r["unit"] or "",
                    "direction": gate.direction(r["unit"]), "message": r["message"] or "",
                    "event_type": r["event_type"], "event_code": r["event_code"]}

        def send(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            rows = con.execute(
                "SELECT * FROM events WHERE day=? AND event_type=1 AND event_code=8"
                " ORDER BY idx DESC LIMIT 30", (day,)).fetchall()
            send({"type": "init", "day": day, "items": [item_of(r) for r in rows]})
            last = con.execute("SELECT COALESCE(MAX(idx),0) m FROM events WHERE day=?", (day,)).fetchone()["m"]
            idle = 0
            while True:
                time.sleep(2.5)
                if dt.date.today().isoformat() != day:
                    send({"type": "reload"})
                    break
                new = con.execute(
                    "SELECT * FROM events WHERE day=? AND idx>? AND event_type=1 AND event_code=8"
                    " ORDER BY idx LIMIT 50", (day, last)).fetchall()
                if new:
                    for r in new:
                        last = max(last, r["idx"])
                    send({"type": "events", "items": [item_of(r) for r in new]})
                    idle = 0
                else:
                    idle += 1
                    if idle % 8 == 0:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            con.close()
            self.close_connection = True

    # -- выгрузки --------------------------------------------------------
    def _export_rows(self, q):
        frm = q.get("from") or dt.date.today().isoformat()
        to = q.get("to") or frm
        view = q.get("view")
        con = gate.connect()
        if view == "absent":
            rows = gate.absent(con, frm, to, group=q.get("group"), search=q.get("search"),
                               user_ptr=q.get("user_ptr") or None, point=qpoints(q))
            con.close()
            return rows, COLS_ABS, frm, to
        if view == "late":
            rows = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                    shift_start=q.get("shift_start"), shift_end=q.get("shift_end"),
                                    user_ptr=q.get("user_ptr") or None, point=qpoints(q))
            con.close()
            return rows, COLS_LATE, frm, to
        rows = gate.attendance(con, frm, to, group=q.get("group"), search=q.get("search"),
                               point=qpoints(q), include_deleted=q.get("deleted") == "1",
                               include_visitors=q.get("visitors") == "1",
                               shift_start=q.get("shift_start"), shift_end=q.get("shift_end"),
                               user_ptr=q.get("user_ptr") or None)
        con.close()
        if view == "summary":
            return gate.attendance_summary(rows), COLS_SUM, frm, to
        return rows, COLS_1C, frm, to

    def export_1c(self, q):
        rows, cols, frm, to = self._export_rows(q)
        enc = q.get("enc", "cp1251")
        sep = {"tab": "\t", "comma": ",", "semicolon": ";"}.get(q.get("sep", "semicolon"), ";")
        dec = q.get("dec", ",")
        data = rows_to_delimited(rows, cols, sep=sep, enc=enc, dec=dec,
                                 header=q.get("header", "1") == "1")
        name = "СКУД_Gate_%s_%s.csv" % (frm, to)
        return self.send_bytes(data, "text/csv; charset=%s" % enc, filename=name,
                               ascii_name="skud_gate_%s_%s.csv" % (frm, to))

    def export_xls(self, q):
        rows, cols, frm, to = self._export_rows(q)
        title = "Посещаемость СКУД Gate за %s" % (frm if frm == to else "%s — %s" % (frm, to))
        data = rows_to_xls(rows, cols, title)
        name = "Посещаемость_%s_%s.xls" % (frm, to)
        return self.send_bytes(data, "application/vnd.ms-excel; charset=utf-8", filename=name,
                               ascii_name="poseshchaemost_%s_%s.xls" % (frm, to))

    def _timesheet(self, q):
        month = (q.get("month") or dt.date.today().strftime("%Y-%m"))[:7]
        try:
            dt.date.fromisoformat(month + "-01")
        except ValueError:
            month = dt.date.today().strftime("%Y-%m")
        group = (q.get("group") or "").strip() or None
        user_ptr = q.get("user_ptr") or None
        in_points = (q.get("in_points") or "").strip() or None
        out_points = (q.get("out_points") or "").strip() or None
        return gate.timesheet(gate.connect(), month, group=group, user_ptr=user_ptr,
                              in_points=in_points, out_points=out_points), month, group

    def _ts_head(self, d, print_mode=True):
        cols = ['<col style="width:3%"><col style="width:14%"><col style="width:9%">']
        for i in range(d["days"]):
            cols.append('<col style="width:%.3f%%">' % (71.0 / d["days"]))
        cols.append('<col style="width:6%">')
        head = "<th>№</th><th>Сотрудник</th><th>Должность</th>"
        today = d.get("today") or 0
        for i, we in enumerate(d["weekend"], 1):
            cls = []
            if we:
                cls.append("we")
            if i == today:
                cls.append("today")
            head += '<th%s><div>%02d</div><div class="wd">%s</div></th>' % (
                (' class="%s"' % " ".join(cls)) if cls else "", i, d["weekday"][i - 1])
        head += '<th class="tot">Итого</th>'
        return "".join(cols), head

    def _ts_body(self, d):
        out = []
        for n, r in enumerate(d["rows"], 1):
            tds = ['<td>%d</td>' % n,
                   '<td class="name">%s</td>' % _esc(r["fio"]),
                   '<td class="pos">%s</td>' % _esc(r["position"] or "")]
            for day in range(1, d["days"] + 1):
                v = r["cells"].get(day)
                cls = []
                if d["weekend"][day - 1]:
                    cls.append("we")
                if day == (d.get("today") or 0):
                    cls.append("today")
                tds.append('<td%s>%s</td>' % ((' class="%s"' % " ".join(cls)) if cls else "",
                                               gate.hm(v) if v else ""))
            tds.append('<td class="tot">%s</td>' % gate.hm(r["total"]))
            out.append("<tr>%s</tr>" % "".join(tds))
        foot = ['<td colspan="3">Итого по дням, ч</td>']
        for i, v in enumerate(d["day_totals"]):
            # за день суммарно сотни часов — в узкой клетке H:MM не влезает
            cell = str(int(round(v / 60.0))) if v else ""
            foot.append('<td%s>%s</td>' % (' class="we"' if d["weekend"][i] else "", cell))
        foot.append('<td class="tot">%s</td>' % gate.hm(d["total"]))
        return "".join(out), "<tr>%s</tr>" % "".join(foot)

    def api_timesheet(self, q):
        d, month, group = self._timesheet(q)
        out = {
            "month": d["month"], "title": d["title"], "days": d["days"],
            "weekend": d["weekend"], "weekday": d["weekday"], "today": d["today"],
            "count": d["count"], "group": group or "",
            "total": gate.hm(d["total"]),
            "day_totals": [gate.hm(x) if x else "" for x in d["day_totals"]],
            "rows": [{
                "fio": r["fio"], "position": r["position"] or "", "group": r["group"] or "",
                "days": r["days"], "total": gate.hm(r["total"]),
                "cells": {str(k): gate.hm(v) for k, v in r["cells"].items()},
            } for r in d["rows"]],
        }
        return self.send_json(out)

    def print_timesheet(self, q):
        d, month, group = self._timesheet(q)
        colgroup, head = self._ts_head(d)
        rows, foot = self._ts_body(d)
        sub = "Период: <b>%s</b> · %s · сотрудников: <b>%d</b>" % (
            _esc(d["title"]),
            "подразделение: " + _esc(group) if group else "все подразделения",
            d["count"])
        html = TIMESHEET_TEMPLATE.format(
            title=_esc(d["title"]), sub=sub, colgroup=colgroup, head=head,
            rows=rows, foot=foot,
            stamp=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
        return self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def export_timesheet_xls(self, q):
        d, month, group = self._timesheet(q)
        colgroup, head = self._ts_head(d)
        rows, foot = self._ts_body(d)
        html = ("<html><head><meta charset='utf-8'><style>"
                "table{border-collapse:collapse;font-family:'Segoe UI',Arial;font-size:11px}"
                "th,td{border:1px solid #b6c2cf;padding:3px 5px;text-align:center}"
                "th{background:#1f6feb;color:#fff}td.name,td.pos{text-align:left}"
                ".we{background:#f1f4f8}td.tot{font-weight:700}</style></head><body>"
                "<h3>Табель учёта рабочего времени · %s</h3>"
                "<table><thead><tr>%s</tr></thead><tbody>%s</tbody><tfoot>%s</tfoot></table>"
                "</body></html>") % (_esc(d["title"]), head, rows, foot)
        name = "Табель_%s.xls" % d["title"].replace(" ", "_")
        return self.send_bytes(html.encode("utf-8"), "application/vnd.ms-excel; charset=utf-8",
                               filename=name, ascii_name="tabel_%s.xls" % month)

    def export_print(self, q):
        view = q.get("view") or "detail"
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()

        if view == "users":
            rows = gate.users_report(con, group=q.get("group"), search=q.get("search"),
                                      user_ptr=q.get("user_ptr") or None)
            cols, title = COLS_USERS, "Отчёт о пользователях"
            subtitle = "Справочник сотрудников и гостевых карт СКУД"
            stats = [("Сотрудников", len(rows)),
                     ("Работает", sum(1 for r in rows if r["status"] == "Работает")),
                     ("Гости / удалены", sum(1 for r in rows if r["status"] != "Работает"))]
            orient = "portrait"
        elif view == "events":
            items = gate.events_list(con, frm, to, etype=q.get("type") or None,
                                     search=(q.get("search") or "").strip() or None,
                                     message=(q.get("message") or "").strip() or None,
                                     user_ptr=q.get("user_ptr") or None,
                                     point=qpoints(q),
                                     alarms_only=q.get("alarms") == "1", limit=2000)
            rows = [dict(it, alarm_flag=("да" if it["alarm"] else "")) for it in items["items"]]
            cols, title = COLS_EVENTS, "Отчёт о событиях СКУД"
            subtitle = "Все события: проходы, двери, тревоги, связь, действия операторов"
            stats = [("Событий", items["total"]),
                     ("Тревог", sum(1 for r in rows if r["alarm_flag"])),
                     ("Показано", len(rows))]
            orient = "landscape"
        else:
            rows, cols, frm, to = self._export_rows(q)
            if view == "summary":
                title = "Свод посещаемости по сотрудникам"
                subtitle = "Дни, часы и опоздания за период"
                stats = [("Сотрудников", len(rows)),
                         ("Человеко-дней", sum(r["days"] for r in rows)),
                         ("Часов всего", round(sum(r["hours"] or 0 for r in rows), 2)),
                         ("Дней с опозданием", sum(r["late_days"] for r in rows))]
                orient = "portrait"
            elif view == "late":
                title = "Опоздания"
                subtitle = "Приход позже начала смены"
                stats = [("Сотрудников", len(rows)),
                         ("Дней с опозданием", sum(r["late_days"] for r in rows)),
                         ("Минут всего", sum(r["late_total"] for r in rows)),
                         ("Максимум за раз", max([r["max_late"] for r in rows] or [0]))]
                orient = "portrait"
            elif view == "absent":
                title = "Сотрудники без проходов"
                subtitle = "Не проходили через СКУД за выбранный период"
                stats = [("Сотрудников", len(rows)), ("Дней в периоде", rows[0]["days"] if rows else 0)]
                orient = "portrait"
            else:
                title = "Учёт рабочего времени"
                subtitle = "Приход, уход и часы по каждому сотруднику"
                stats = [("Записей", len(rows)),
                         ("Сотрудников", len({r["user_ptr"] for r in rows})),
                         ("Часов всего", round(sum(r["hours"] or 0 for r in rows), 2)),
                         ("Дней с опозданием", sum(1 for r in rows if r["late"]))]
                orient = "landscape"
        con.close()

        def esc(v):
            return (str(v if v is not None else "")
                    .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        head = "".join('<th%s>%s</th>' % (' class="num"' if k in NUM_KEYS else "", esc(col_title(t)))
                       for k, t in cols)
        trs = []
        for r in rows:
            tds = []
            for key, _ in cols:
                v = r.get(key, "")
                if key in ("hours", "avg_hours") and isinstance(v, float):
                    v = ("%.2f" % v).replace(".", ",")
                cls = ' class="num"' if key in ("enter", "exit", "hours", "passes", "late", "early",
                                                "day", "days", "avg_hours", "late_days", "late_total",
                                                "avg_late", "max_late", "time", "alarm_flag") else ""
                if key == "alarm_flag" and v:
                    tds.append('<td class="num alarm">да</td>')
                else:
                    tds.append("<td%s>%s</td>" % (cls, esc(v)))
            trs.append("<tr>%s</tr>" % "".join(tds))
        stats_html = "".join('<div class="stat"><span>%s</span><b>%s</b></div>' % (esc(l), esc(v))
                             for l, v in stats)
        period = frm if frm == to else "%s — %s" % (frm, to)
        html = PRINT_TEMPLATE.format(
            title=esc(title), subtitle=esc(subtitle), period=esc(period), head=head,
            rows="\n".join(trs), stats=stats_html, n=len(rows),
            stamp=dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
            orient=orient, src=esc(gate.CFG.get("share", "")))
        return self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    # -- POST ------------------------------------------------------------
    def do_POST(self):
        path, q = self.q()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if path == "/login":
            form = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
            login = (form.get("username") or "").strip()
            if check_password(login, form.get("password", "")):
                cookie = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax" % (
                    COOKIE, make_token(login), SESSION_HOURS * 3600)
                return self.redirect("/", cookie=cookie)
            return self.redirect("/login?e=1")
        if not self.current_user():
            return self.send_json({"error": "unauthorized"}, code=401)
        if path == "/api/sync":
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                payload = {}
            return self.send_json(do_sync(days=payload.get("days")))
        if path.startswith("/api/accounts") or path.startswith("/api/settings"):
            return self.admin_post(path, body)
        if path.startswith("/api/passes"):
            return self.passes_post(path, body)
        return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)


PRINT_TEMPLATE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>{title} · {period}</title>
<style>
 @page{{size:A4 {orient};margin:10mm 8mm}}
 body{{font:11px/1.35 "Segoe UI",Arial,sans-serif;color:#111;margin:0;padding:0}}
 .toolbar{{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:0 0 8px}}
 .toolbar .hint{{color:#667;font-size:10.5px}}
 .toolbar button{{font:13px "Segoe UI",Arial;padding:7px 16px;border:1px solid #2f6fd0;border-radius:3px;
   background:#2f6fd0;color:#fff;cursor:pointer}}
 @media print{{.toolbar{{display:none}}}}
 .doc-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
   border-bottom:2px solid #2f6fd0;padding-bottom:6px;margin-bottom:9px}}
 .doc-head h1{{font-size:15px;margin:0 0 2px;font-weight:600}}
 .doc-head .sub{{color:#555;font-size:10.5px}}
 .doc-head .r{{text-align:right;font-size:10px;color:#444;line-height:1.5;white-space:nowrap}}
 .doc-head .r b{{color:#111}}
 .stats{{display:flex;gap:8px;margin:0 0 9px;flex-wrap:wrap}}
 .stat{{border:1px solid #cfd8e3;border-radius:3px;padding:3px 10px;min-width:96px}}
 .stat span{{display:block;color:#667;font-size:9px;text-transform:uppercase;letter-spacing:.4px}}
 .stat b{{display:block;font-size:14px;font-weight:600;line-height:1.2}}
 table{{width:100%;border-collapse:collapse;font-size:10px}}
 thead{{display:table-header-group}}
 th{{background:#eef2f6;border:1px solid #b9c4d0;padding:4px 6px;text-align:left;
   font-size:9.5px;font-weight:600;color:#333}}
 td{{border:1px solid #d7dee6;padding:3px 6px;vertical-align:top}}
 tbody tr:nth-child(even) td{{background:#f7f9fb}}
 td.num{{text-align:center;white-space:nowrap}}
 td.alarm{{color:#b42318;font-weight:700}}
 tr{{page-break-inside:avoid}}
 .foot{{margin-top:8px;padding-top:5px;border-top:1px solid #d7dee6;color:#777;font-size:9px;
   display:flex;justify-content:space-between}}
</style></head><body>
<div class="toolbar"><span class="hint">Проверьте форму и нажмите «Печать» (или Ctrl+P)</span><button onclick="window.print()">Печать</button></div>
<div class="doc-head">
  <div class="l"><h1>{title}</h1><div class="sub">{subtitle}</div></div>
  <div class="r">Период: <b>{period}</b><br>Записей: <b>{n}</b><br>Сформировано: {stamp}<br>СКУД Gate-IP</div>
</div>
<div class="stats">{stats}</div>
<table><thead><tr>{head}</tr></thead><tbody>
{rows}
</tbody></table>
<div class="foot"><span>СКУД Gate-IP</span></div>
</body></html>"""


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    gate.init_db()
    try:
        gate.sync_config()                       # картотека считывается при старте
    except Exception as exc:                     # noqa: BLE001
        print("картотека Gate не загружена:", exc, flush=True)
    if accounts.ensure_admin(AUTH):
        print("создан администратор из gate.config.json → auth", flush=True)
    threading.Thread(target=sync_worker, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("СКУД Gate: http://0.0.0.0:%d/  вход: %s  (Ctrl+C — стоп)" % (port, AUTH_USER), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PASS_TEMPLATE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Пропуск {number}</title>
<style>
 @page{{size:A6 landscape;margin:8mm}}
 body{{font:12px/1.4 "Segoe UI",Arial,sans-serif;color:#111;margin:0}}
 .toolbar{{position:fixed;top:8px;right:10px}}
 .toolbar button{{font:13px "Segoe UI",Arial;padding:6px 14px;border:1px solid #2f6fd0;border-radius:3px;
   background:#2f6fd0;color:#fff;cursor:pointer}}
 @media print{{.toolbar{{display:none}}}}
 .card{{border:2px solid #2f6fd0;border-radius:6px;padding:10px 14px;max-width:520px}}
 .head{{display:flex;justify-content:space-between;align-items:flex-start;
   border-bottom:1px solid #cfd8e3;padding-bottom:6px;margin-bottom:8px}}
 .head .t{{font-size:11px;color:#555;letter-spacing:.6px;text-transform:uppercase}}
 .head .n{{font-size:15px;font-weight:700}}
 .who{{font-size:17px;font-weight:700;margin:2px 0 2px}}
 .org{{color:#444;margin-bottom:8px}}
 table{{width:100%;border-collapse:collapse;font-size:11px}}
 td{{padding:2px 0;vertical-align:top}}
 td.k{{color:#667;width:96px;white-space:nowrap}}
 .doors{{margin-top:6px;padding:5px 8px;background:#eef5ff;border:1px solid #cfe0f7;border-radius:3px;font-size:11px}}
 .foot{{margin-top:8px;border-top:1px dashed #cfd8e3;padding-top:6px;font-size:10px;color:#666;
   display:flex;justify-content:space-between}}
 .state{{font-size:10px;color:#2f6fd0;border:1px solid #cfe0f7;background:#eef5ff;border-radius:3px;padding:1px 6px}}
 .mono{{font-family:ui-monospace,Consolas,monospace}}
</style></head><body>
<div class="toolbar"><button onclick="window.print()">Печать</button></div>
<div class="card">
  <div class="head">
    <div><div class="t">СКУД Gate · пропуск</div><div class="n">№ {number}</div></div>
    <div class="state">{state}</div>
  </div>
  <div class="who">{visitor}</div>
  <div class="org">{position} · {org}</div>
  <table>
    <tr><td class="k">Дата приёма</td><td><b>{visit}</b></td></tr>
    <tr><td class="k">Действует до</td><td><b>{valid_to}</b></td></tr>
    <tr><td class="k">График</td><td>{schedule}</td></tr>
    <tr><td class="k">Карта</td><td class="mono">{card}</td></tr>
    <tr><td class="k">К кому</td><td>{host}</td></tr>
    <tr><td class="k">Цель</td><td>{purpose}</td></tr>
    <tr><td class="k">Документ</td><td>{document}</td></tr>
    <tr><td class="k">Телефон</td><td>{phone}</td></tr>
  </table>
  <div class="doors"><b>Двери:</b> {doors}</div>
  <div class="foot"><span>Выдал: {author} · {created}</span><span>Подпись ________</span></div>
</div>
<script>window.addEventListener('load',function(){{setTimeout(function(){{window.print();}},350);}});</script>
</body></html>"""


TIMESHEET_TEMPLATE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Табель · {title}</title>
<style>
 @page{{size:A4 landscape;margin:8mm 6mm}}
 body{{font:10px/1.25 "Segoe UI",Arial,sans-serif;color:#111;margin:0}}
 .toolbar{{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:0 0 6px}}
 .toolbar .hint{{color:#667;font-size:10.5px}}
 .toolbar button{{font:13px "Segoe UI",Arial;padding:6px 14px;border:1px solid #2f6fd0;
   border-radius:3px;background:#2f6fd0;color:#fff;cursor:pointer}}
 @media print{{.toolbar{{display:none}}}}
 h1{{font-size:15px;margin:0 0 2px;font-weight:600}}
 .sub{{color:#555;font-size:10.5px;margin-bottom:8px}}
 table{{width:100%;border-collapse:collapse;table-layout:fixed}}
 th,td{{border:1px solid #c6cfd9;padding:1px 0;text-align:center;font-size:9.5px;
   font-family:"Arial Narrow","Liberation Sans Narrow","Segoe UI",Arial,sans-serif}}
 th{{background:#eef2f6;font-weight:600}}
 td.name,td.pos{{text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
 th.we,td.we{{background:#edf1f6}}
 th.we>div:first-child{{color:#b42318}}
 th .wd{{font-weight:400;color:#78828f;font-size:8px;line-height:1.15}}
 th.we .wd{{color:#b42318}}
 th.today,td.today{{background:#e8f1ff}}
 th.today{{box-shadow:inset 0 -2px 0 #2f6fd0}}
 th.tot,td.tot{{background:#f7f9fb;font-weight:700}}
 tfoot td{{background:#eef2f6;font-weight:600;font-size:7.5px;padding:1px 0}}
</style></head><body>
<div class="toolbar"><span class="hint">Проверьте табель и нажмите «Печать» (или Ctrl+P)</span><button onclick="window.print()">Печать</button></div>
<h1>Табель учёта рабочего времени</h1>
<div class="sub">{sub} · сформировано {stamp}</div>
<table>
<colgroup>{colgroup}</colgroup>
<thead><tr>{head}</tr></thead>
<tbody>{rows}</tbody>
<tfoot>{foot}</tfoot>
</table>
</body></html>"""


if __name__ == "__main__":
    main()

